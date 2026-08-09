"""
HARNESS-002A §4 — the semantic compiler: prose becomes a graph, or is refused by name.

    exact prompt + accepted InquiryFrame + SceneReading
      -> atomic typed claims, anchored to where their words came from
      -> relations between them
      -> observable requirements, with alternatives where operationalization is plural
      -> decision candidates, semantic remainder, refusals

IT READS WORDS. The compiler is not given the images — its job is to atomize and type what has
already been said, and a compiler that could look would start adding claims nobody made and
anchoring them to a source pointer that resolves to nothing.

IT NAMES NO INSTRUMENT. An observable requests a capability CLASS. The step from `extent` to
`concept_segment` belongs to the broker, downstream, where the live catalogue is; taken here it
would turn "no instrument exists for this" into a planning error instead of a visible gap. This is
the one thing the existing `argument_planner` does that this module deliberately does NOT reuse:
its sub-claim/support/complicate/challenge vocabulary is reused verbatim, its premature
claim-to-actuator binding is not.

## What is refused, and what is merely corrected downward

Two different failures, handled two different ways, and the split is deliberate.

  AN INVENTION IS REFUSED BY NAME. A claim kind, capability class, ground form or edge kind outside
  the closed sets is not mapped to the nearest neighbour: the value is dropped, a refusal quotes it
  verbatim, and the object that depended on it goes with it. How often a model invents a capability
  is the only observable that says whether to trust it, and a silently corrected invention is
  unobservable.

  A CONSTRAINT VIOLATION IS CORRECTED DOWNWARD, AND RECORDED. A model that types an interpretation
  as `measurable`, or a claim as `measured`, has stated an ASPIRATION rather than an instruction —
  `argument_planner._normalise_status` makes exactly this distinction. Coercion in the safe
  direction can only make a claim look weaker than the model hoped, never stronger, and it keeps a
  real sentence in the graph instead of deleting it over a field the model was never allowed to
  set. The refusal is still recorded, so the attempt is visible.

## No fallback

There is no rule-based compiler. `GroqArgumentPlanner` gives the reason and it holds one level up:
nothing rule-based can atomize a thesis into claims, so a fallback here would have to INVENT a
decomposition, which is the single worst failure this module has. An unavailable compiler produces
an empty graph that says the compiler was unavailable.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (CallTopology, CapabilityClass, ClaimEdge,
                                                  ClaimEdgeKind, ClaimKind, ClaimNode, ClaimStatus,
                                                  CompilerRefusal, CompilerRefusalKind,
                                                  DecisionCandidate, DecisionKind,
                                                  FORBIDDEN_INITIAL_STATUSES, GraphProvenance,
                                                  GroundForm, ImageScope, ModelReceipt,
                                                  NON_MEASURING_CLASSES, ObservableSpec,
                                                  OperationalAlternative,
                                                  SemanticInquiryGraph, SemanticRemainderItem,
                                                  SourcePointer, SourceType,
                                                  _FORBIDDEN_DEMANDS, _REQUIRED_DEMANDS)
from backend.services import role_registry

from . import contracts, ids
from .base import CompilationRequest, refusal, sha256_of

ROLE = "semantic_compiler"
PRODUCER = "semantic_compilation/compiler-v1"

#: A graph with more claims than this is a transcript, not a decomposition. Applied after parsing;
#: the overflow is REPORTED, never trimmed silently.
MAX_CLAIMS = 60
MAX_OBSERVABLES_PER_CLAIM = 4

SYSTEM_PROMPT = (
    "You are a semantic compiler inside a visual close-reading tool. You are given a person's "
    "PROMPT, a structured reading of that prompt (which was produced WITHOUT seeing any image), "
    "and a provisional visual READING of the images produced by a vision model. You do not see the "
    "images yourself. You output JSON and nothing else.\n\n"
    "Your job is to turn prose into an inspectable graph:\n"
    "1. ATOMIZE. One claim per sentence-worth of content. A compound sentence becomes several "
    "claims. Do not summarise.\n"
    "2. ANCHOR. Every claim names where its words came from: the prompt, the frame, or a reading "
    "block id. A claim you derived yourself is `compiler_inference` and must name the claims you "
    "derived it from.\n"
    "3. TYPE. Give every claim a kind from the closed list. `unknown` is a legitimate answer and is "
    "better than a confident wrong type.\n"
    "4. SEPARATE. An ENTITY (a thing is present) is not a RELATION (two things stand somehow) and "
    "neither is an INTERPRETATION (it reads as something). A one-image observation is not a corpus "
    "tendency — say which by setting `image_scope`.\n"
    "5. RELATE. Connect claims with supports / complicates / challenges / composes_from / "
    "generalizes.\n"
    "6. OPERATIONALIZE. For each claim that could be investigated, say what would have to become "
    "OBSERVABLE. Request a capability CLASS, never a tool. Do not jump from a phrase straight to "
    "an implementation.\n"
    "7. SAY WHAT MEASUREMENT WOULD NOT REACH. `semantic_remainder` is first-class. An interpretive "
    "prompt with an empty remainder is a wrong answer.\n"
    "8. OFFER ALTERNATIVES where more than one honest operationalization exists, and raise a "
    "DECISION only where choosing between them would materially change the investigation. "
    "Uncertainty alone is not a reason to interrupt somebody.\n\n"
    "Hard rules:\n"
    "- Never output a mask, box, point, polygon, coordinate, pixel count, region id, mark id or "
    "confidence value. Nothing has been measured and you have not seen anything.\n"
    "- Never mark a claim `visible` or `measured`. Nothing has run.\n"
    "- A claim whose warrant is outside the picture (a period, a school, an influence) is "
    "`historical_or_sourced` and asks for `sourced`, never `measurable`. It may only request the "
    "`external_source` capability class.\n"
    "- An INTERPRETATION does not become measurable because measurements contribute to it. Say "
    "what contributes, in the semantic remainder, and leave the interpretation interpretive.\n"
    "- A rule for making something that does not exist is a `generative_rule` and is `imagined`.\n"
    "- Keep claims you cannot operationalise. Do not drop them to make the graph look complete."
)


def _vocabulary_block() -> str:
    contract = contracts.graph_contract()
    return json.dumps({
        "claim_kinds": contract["claim_kinds"],
        "claim_edge_kinds": list(contracts.closed_set("claim_edge_kinds")),
        "epistemic_demands": list(contracts.closed_set("epistemic_demands")),
        "claim_statuses": list(contracts.closed_set("claim_statuses")),
        "image_scopes": list(contracts.closed_set("image_scopes")),
        "source_types": list(contracts.closed_set("source_types")),
        "capability_classes": contract["capability_classes"],
        "ground_forms": contract["ground_forms"],
        "decision_kinds": list(contracts.closed_set("decision_kinds")),
    }, indent=2)


def _frame_digest(frame: Mapping[str, Any]) -> Dict[str, Any]:
    """The frame, compacted to what a compiler can use, with its own provenance kept separate.

    Deliberately NOT merged into the reading. "The user said 'sensuality'" and "a VLM thought the
    drapery looked soft" are different warrants, and a compiler handed one undifferentiated context
    would anchor claims to whichever it happened to read last.
    """
    def _rows(key: str) -> List[Any]:
        raw = frame.get(key)
        return list(raw) if isinstance(raw, (list, tuple)) else []

    return {
        "mode": getattr(frame.get("mode"), "value", frame.get("mode")),
        "requested_output": frame.get("requested_output"),
        "attentions": [{"term": r.get("term"), "category": r.get("category")}
                       for r in _rows("attentions") if isinstance(r, Mapping)],
        "epistemic_demands": [{"clause": r.get("clause"), "term": r.get("term"),
                               "kind": getattr(r.get("kind"), "value", r.get("kind")),
                               "why": r.get("why")}
                              for r in _rows("epistemic_demands") if isinstance(r, Mapping)],
        "unresolved_terms": [{"term": r.get("term"), "why": r.get("why")}
                             for r in _rows("unresolved_terms") if isinstance(r, Mapping)],
        "semantic_remainder": [{"term": r.get("term"), "why": r.get("why")}
                               for r in _rows("semantic_remainder") if isinstance(r, Mapping)],
    }


def build_prompt(request: CompilationRequest) -> str:
    reading = request.reading
    blocks = [{"block_id": b.block_id, "kind": b.kind.value, "text": b.text,
               "images": list(b.image_refs)} for b in (reading.blocks if reading else ())]
    return (
        f"THE PERSON'S PROMPT, verbatim:\n{request.prompt}\n\n"
        f"THE PROMPT-ONLY FRAME — produced without seeing any image. These are the person's own "
        f"words and how they were read:\n{json.dumps(_frame_digest(request.inquiry_frame), indent=2)}\n\n"
        f"THE VISUAL READING — a vision model's provisional reading of the images. INTERPRETIVE, "
        f"not evidence. Anchor to a block by its `block_id`:\n"
        f"{json.dumps({'text': reading.text if reading else '', 'blocks': blocks}, indent=2)}\n\n"
        f"THE IMAGES available, by id:\n"
        f"{json.dumps([{'post_id': i.post_id, 'title': i.title} for i in request.images])}\n\n"
        f"THE VOCABULARY — use only these:\n{_vocabulary_block()}\n\n"
        f"Return JSON of exactly this shape. `ref` values are yours to invent and are used only to "
        f"link objects within this response:\n"
        f'{{"claims": [{{"ref": "c1", "text": "<one atomic claim>", '
        f'"kind": "<claim kind>", "subject": "", "predicate": "", "object": "", '
        f'"image_scope": "<image scope>", "demand": "<epistemic demand>", '
        f'"status": "<claim status>", "inferred_from": ["c0"], '
        f'"sources": [{{"type": "<source type>", "source_id": "prompt|<block_id>", '
        f'"text": "<the words, verbatim from that source>"}}]}}], '
        f'"edges": [{{"kind": "<edge kind>", "from": "c1", "to": "c2", "why": ""}}], '
        f'"observables": [{{"ref": "o1", "claim": "c1", "kind": "<what to observe>", '
        f'"targets": ["<what to look at>"], "image_scope": "<image scope>", '
        f'"capability_classes": ["<capability class>"], "ground_forms": ["<ground form>"], '
        f'"success_when": "", "ambiguous_when": "", "refused_when": "", '
        f'"remains_interpretive": "<what is still a reading even if this succeeds>", '
        f'"alternatives": [{{"label": "", "consequence": "", "capability_classes": [], '
        f'"ground_forms": [], "recommended": false}}]}}], '
        f'"decisions": [{{"kind": "<decision kind>", "question": "", '
        f'"why_now": "<what changes downstream>", "affects": ["c1", "o1"], "blocking": false, '
        f'"options": [{{"label": "", "consequence": "", "recommended": false}}]}}], '
        f'"semantic_remainder": [{{"term": "", "why": "", '
        f'"contributing_capability_classes": [], "claims": ["c1"]}}]}}\n'
        f"Return empty lists rather than inventing content for any field."
    )


# ── parsing helpers ──────────────────────────────────────────────────────────

def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _rows(payload: Mapping[str, Any], key: str) -> List[Mapping[str, Any]]:
    raw = payload.get(key)
    return [r for r in raw if isinstance(r, Mapping)] if isinstance(raw, list) else []


def _enum_list(raw: Any, enum_cls, set_name: str, kind: CompilerRefusalKind, where: str,
               inquiry_id: str, refusals: List[CompilerRefusal]) -> List[Any]:
    """Closed-set members, with every invention refused BY NAME and dropped."""
    values = [str(v).strip() for v in raw or () if str(v).strip()]
    unknown = contracts.unknown_values(values, set_name)
    for name in unknown:
        refusals.append(refusal(
            inquiry_id, kind, name,
            f"not one of {list(contracts.closed_set(set_name))}. Refused by name rather than "
            f"mapped to the nearest-looking member: a model's invented vocabulary is the only "
            f"signal that says whether to trust the rest of what it produced.",
            detail=[where]))
    out: List[Any] = []
    for value in values:
        if value in unknown:
            continue
        member = enum_cls(value)
        if member not in out:
            out.append(member)
    return out


class _Compilation:
    """One parse, in one object, because the pieces genuinely need each other.

    The local refs a model invents (`c1`, `o1`) are resolved to content-derived ids here, and every
    later reference is checked against what actually survived. A model whose claim was dropped for
    naming an invented kind must not leave an edge pointing at it.
    """

    def __init__(self, request: CompilationRequest):
        self.request = request
        self.inquiry_id = request.inquiry_id
        self.refusals: List[CompilerRefusal] = list(request.inherited_refusals)
        self.notes: List[str] = list(request.inherited_notes)
        self.claims: List[ClaimNode] = []
        #: Claims survive parsing as plain dicts and are only CONSTRUCTED once every local ref is
        #: known. `ClaimNode` refuses an inference with no parents, and the parents cannot be
        #: resolved on the first pass — a claim may legitimately name one the model listed after it.
        self.pending: List[Dict[str, Any]] = []
        self.by_ref: Dict[str, str] = {}
        self.observable_by_ref: Dict[str, str] = {}
        self.block_ids: Set[str] = {b.block_id for b in
                                    (request.reading.blocks if request.reading else ())}
        self.prompt_normal = ids.normalise(request.prompt)

    def refuse(self, kind: CompilerRefusalKind, what: str, why: str,
               detail: Sequence[str] = ()) -> None:
        self.refusals.append(refusal(self.inquiry_id, kind, what, why, detail))

    # ── source pointers ──
    def pointers(self, rows: Sequence[Mapping[str, Any]], where: str) -> List[SourcePointer]:
        out: List[SourcePointer] = []
        for row in rows:
            raw_type = _text(row.get("type")) or _text(row.get("source_type"))
            if raw_type not in set(contracts.closed_set("source_types")):
                self.refuse(CompilerRefusalKind.UNKNOWN_SOURCE_TYPE, raw_type or "(empty)",
                            f"not one of {list(contracts.closed_set('source_types'))}; the pointer "
                            f"was dropped rather than guessed at.", detail=[where])
                continue
            source_type = SourceType(raw_type)
            source_id = _text(row.get("source_id")) or (
                "prompt" if source_type is SourceType.PROMPT else "")
            text = _text(row.get("text"))

            if source_type is SourceType.SCENE_READING and source_id not in self.block_ids:
                self.refuse(CompilerRefusalKind.DANGLING_REFERENCE, source_id or "(empty)",
                            "the compiler anchored a claim to a reading block that is not in this "
                            "reading. The pointer was dropped; a claim left with no pointer at all "
                            "is refused as unanchored.", detail=[where])
                continue

            span: Optional[Tuple[int, int]] = None
            if source_type is SourceType.PROMPT and text:
                # The span is COMPUTED, never taken from the model. A model asked for character
                # offsets will confidently invent them, and an invented span renders in a UI as a
                # highlight over words the person did not write.
                found = self.request.prompt.lower().find(text.lower())
                if found >= 0:
                    span = (found, found + len(text))
                elif ids.normalise(text) not in self.prompt_normal:
                    self.notes.append(
                        f"{where}: the compiler quoted {text[:60]!r} as being from the prompt and "
                        f"it is not there verbatim. The pointer was kept and its span left unset, "
                        f"so nothing highlights words the person did not write.")

            out.append(SourcePointer(source_type=source_type, source_id=source_id or "prompt",
                                     text=text, span=span,
                                     image_refs=[str(i) for i in row.get("images") or ()
                                                 if str(i).strip()]))
        return out

    # ── claims ──
    def claim(self, index: int, row: Mapping[str, Any]) -> None:
        where = f"claim {index}"
        found = contracts.geometry_keys_in(row)
        if found:
            self.refuse(CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                        "a compiled claim may not carry geometry, a region id or a confidence. "
                        "Nothing has been measured. The claim was dropped rather than stripped.",
                        detail=[where, _text(row.get("text"))[:160]])
            return

        text = _text(row.get("text")) or _text(row.get("claim"))
        if not text:
            return

        raw_kind = _text(row.get("kind")) or _text(row.get("claim_kind"))
        if raw_kind not in set(contracts.closed_set("claim_kinds")):
            self.refuse(CompilerRefusalKind.UNKNOWN_CLAIM_KIND, raw_kind or "(empty)",
                        f"not one of {list(contracts.closed_set('claim_kinds'))}. The claim was "
                        f"dropped rather than filed under `unknown`: `unknown` means the compiler "
                        f"could not type it, and using it here would hide an invented vocabulary "
                        f"inside a legitimate one.",
                        detail=[where, text[:160]])
            return
        kind = ClaimKind(raw_kind)

        demand = self._demand(row, kind, where)
        status = self._status(row, where)
        scope = self._scope(row, kind, where)

        pointers = self.pointers(_rows(row, "sources"), where)
        parents = [str(p).strip() for p in row.get("inferred_from") or () if str(p).strip()]
        if not pointers:
            if parents:
                pointers = [SourcePointer(source_type=SourceType.COMPILER_INFERENCE,
                                          source_id="compiler", text=text)]
            else:
                self.refuse(CompilerRefusalKind.UNANCHORED_CLAIM, text[:120],
                            "the compiler produced a claim with no source pointer and no parent "
                            "claim. An unanchored claim is one nobody said and nothing produced, "
                            "and it reads exactly like the others.", detail=[where])
                return
        if all(p.source_type is SourceType.COMPILER_INFERENCE for p in pointers) and not parents:
            self.refuse(CompilerRefusalKind.INFERENCE_WITHOUT_PARENT, text[:120],
                        "an inference with no parents is an assertion wearing an inference's "
                        "clothes.", detail=[where])
            return

        claim_id = ids.claim_id(self.inquiry_id, kind, text)
        local = _text(row.get("ref")) or f"#{index}"
        self.by_ref[local] = claim_id
        if any(p["claim_id"] == claim_id for p in self.pending):
            # Content-derived ids collapse a repeat rather than duplicating it. A model repeats
            # itself; two identical claims are one claim.
            return
        self.pending.append({
            "claim_id": claim_id, "text": text, "claim_kind": kind,
            "subject": _text(row.get("subject")), "predicate": _text(row.get("predicate")),
            "object": _text(row.get("object")), "vocabulary": _text(row.get("vocabulary")),
            "sources": pointers, "image_scope": scope, "epistemic_demand": demand,
            "status": status, "note": _text(row.get("note")),
            "parents": parents, "where": where})

    def _demand(self, row: Mapping[str, Any], kind: ClaimKind, where: str) -> DemandKind:
        raw = _text(row.get("demand")) or _text(row.get("epistemic_demand"))
        if raw and raw not in {d.value for d in DemandKind}:
            self.refuse(CompilerRefusalKind.UNKNOWN_DEMAND_KIND, raw,
                        f"not one of {[d.value for d in DemandKind]}. Read as `interpretive`, which "
                        f"is the only direction with no way to overstate: guessing `measurable` "
                        f"would claim an instrument could settle something nobody named.",
                        detail=[where])
            raw = ""
        demand = DemandKind(raw) if raw else DemandKind.INTERPRETIVE

        forbidden = _FORBIDDEN_DEMANDS.get(kind)
        if forbidden and demand in forbidden:
            corrected = (DemandKind.SOURCED if kind is ClaimKind.HISTORICAL_OR_SOURCED
                         else DemandKind.INTERPRETIVE)
            self.refuse(CompilerRefusalKind.MEASURED_STATUS_CLAIMED, demand.value,
                        f"a {kind.value!r} claim may not ask for a measurement. Corrected DOWNWARD "
                        f"to {corrected.value!r} and recorded: a demand is an aspiration rather "
                        f"than an instruction, and correcting it down can only make the claim look "
                        f"weaker than the compiler hoped, never stronger.",
                        detail=[where])
            return corrected
        required = _REQUIRED_DEMANDS.get(kind)
        if required and demand not in required:
            corrected = sorted(required, key=lambda d: d.value)[0]
            self.refuse(CompilerRefusalKind.UNKNOWN_DEMAND_KIND, demand.value,
                        f"a {kind.value!r} claim must ask for one of "
                        f"{sorted(d.value for d in required)}. Corrected to {corrected.value!r}: a "
                        f"rule for making what does not exist has nothing to measure and nothing "
                        f"to cite.", detail=[where])
            return corrected
        return demand

    def _status(self, row: Mapping[str, Any], where: str) -> ClaimStatus:
        raw = _text(row.get("status")).lower()
        if raw in FORBIDDEN_INITIAL_STATUSES:
            self.refuse(CompilerRefusalKind.MEASURED_STATUS_CLAIMED, raw,
                        f"nothing has run, so no claim may start {raw!r}. Read as `uncertain`. A "
                        f"compiler that could mint a measured claim would make the whole evidence "
                        f"layer decorative.", detail=[where])
            return ClaimStatus.UNCERTAIN
        if raw and raw not in {s.value for s in ClaimStatus}:
            self.refuse(CompilerRefusalKind.UNKNOWN_CLAIM_STATUS, raw,
                        f"not one of {[s.value for s in ClaimStatus]}. Read as `uncertain`, which "
                        f"is the only direction that cannot overstate. Named rather than quietly "
                        f"coerced: every other invention in this parser is counted, and a status "
                        f"nobody declared is how a vocabulary drifts one word at a time.",
                        detail=[where])
            return ClaimStatus.UNCERTAIN
        return ClaimStatus(raw) if raw else ClaimStatus.INTERPRETIVE

    def _scope(self, row: Mapping[str, Any], kind: ClaimKind, where: str) -> ImageScope:
        raw = _text(row.get("image_scope"))
        scope = ImageScope(raw) if raw in {s.value for s in ImageScope} else ImageScope.CORPUS
        if kind is ClaimKind.COMPARISON and scope is ImageScope.ONE_IMAGE:
            self.refuse(CompilerRefusalKind.IMAGE_SCOPE_CORRECTED, "one_image",
                        "a comparison scoped to one image. One observation typed as a corpus "
                        "tendency is the cheapest way to manufacture a finding, so the scope was "
                        "widened to `corpus` and the correction recorded.", detail=[where])
            return ImageScope.CORPUS
        return scope

    def build_claims(self) -> None:
        """Resolve every local ref, then construct. Two passes, and the order is forced.

        A claim may legitimately name a parent the model listed after it, so parents cannot be
        resolved during the first pass. And dropping one claim can orphan another's parent, so the
        drop runs to a FIXPOINT — a single pass would leave an inference standing on a parent that
        had itself been refused, which is the assertion-wearing-inference's-clothes shape one
        remove away.
        """
        if len(self.pending) > MAX_CLAIMS:
            self.notes.append(f"the compiler produced {len(self.pending)} claims; kept the first "
                              f"{MAX_CLAIMS}")
            self.pending = self.pending[:MAX_CLAIMS]

        # THE LOOP DECIDES; THE REFUSALS ARE WRITTEN AFTER IT SETTLES. Refusing inside the loop
        # emitted the same dangling parent once per iteration, so a graph that needed two rounds
        # reported twice as many refusals as it had problems — and a refusal count is exactly the
        # number a reader uses to judge how much of a model's output survived.
        live = {p["claim_id"] for p in self.pending}
        orphaned: List[Dict[str, Any]] = []
        while True:
            dropped: Set[str] = set()
            for entry in self.pending:
                entry["resolved_parents"] = self._parents_of(entry, live)
                if not entry["resolved_parents"] and all(
                        p.source_type is SourceType.COMPILER_INFERENCE for p in entry["sources"]):
                    dropped.add(entry["claim_id"])
                    orphaned.append(entry)
            if not dropped:
                break
            live -= dropped
            self.pending = [p for p in self.pending if p["claim_id"] not in dropped]

        # OVER THE ORPHANS TOO. Scanning only the survivors traded the duplicate for a SILENT DROP,
        # which is worse in kind: a claim refused for naming a parent that never existed would take
        # the record of that invention down with it, and the invention is the thing worth counting.
        for entry in [*self.pending, *orphaned]:
            for ref in entry["parents"]:
                target = self.by_ref.get(ref)
                if target is None or target not in live or target == entry["claim_id"]:
                    self.refuse(
                        CompilerRefusalKind.DANGLING_REFERENCE, str(ref),
                        "a claim was said to be inferred from something that is not in the graph. "
                        "The parent link was dropped.", detail=[entry["where"]])
        for entry in orphaned:
            self.refuse(
                CompilerRefusalKind.INFERENCE_WITHOUT_PARENT, entry["text"][:120],
                "every parent this inference named was dropped, leaving an assertion wearing an "
                "inference's clothes. The claim went with them.", detail=[entry["where"]])

        for entry in self.pending:
            self.claims.append(ClaimNode(
                claim_id=entry["claim_id"], text=entry["text"], claim_kind=entry["claim_kind"],
                subject=entry["subject"], predicate=entry["predicate"], object=entry["object"],
                vocabulary=entry["vocabulary"], sources=entry["sources"],
                image_scope=entry["image_scope"], epistemic_demand=entry["epistemic_demand"],
                status=entry["status"], inferred_from=entry["resolved_parents"],
                note=entry["note"]))

    def _parents_of(self, entry: Mapping[str, Any], live: Set[str]) -> List[str]:
        resolved: List[str] = []
        for ref in entry["parents"]:
            target = self.by_ref.get(ref)
            if target is None or target not in live or target == entry["claim_id"]:
                continue
            if target not in resolved:
                resolved.append(target)
        return resolved


def _alternatives(comp: _Compilation, rows: Sequence[Mapping[str, Any]],
                  owner_id: str, where: str) -> List[OperationalAlternative]:
    out: List[OperationalAlternative] = []
    for row in rows:
        label = _text(row.get("label"))
        if not label:
            continue
        classes = _enum_list(row.get("capability_classes"), CapabilityClass, "capability_classes",
                             CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS, where,
                             comp.inquiry_id, comp.refusals)
        grounds = _enum_list(row.get("ground_forms"), GroundForm, "ground_forms",
                             CompilerRefusalKind.UNKNOWN_GROUND_FORM, where,
                             comp.inquiry_id, comp.refusals)
        out.append(OperationalAlternative(
            alternative_id=ids.alternative_id(comp.inquiry_id, owner_id, label), label=label,
            consequence=_text(row.get("consequence")), capability_classes=classes,
            ground_forms=grounds, description=_text(row.get("description")),
            recommended=bool(row.get("recommended"))))
    # De-duplicated by id, so a model repeating an option does not produce a fork with the same
    # branch twice — which reads as a real choice and is not one.
    seen: Dict[str, OperationalAlternative] = {}
    for alt in out:
        seen.setdefault(alt.alternative_id, alt)
    return list(seen.values())


def _compile_payload(request: CompilationRequest, payload: Any,
                     receipt: ModelReceipt) -> SemanticInquiryGraph:
    """Raw model JSON → a validated graph. The single parse path, shared by replay and live."""
    comp = _Compilation(request)

    if not isinstance(payload, Mapping):
        comp.refuse(CompilerRefusalKind.UNPARSEABLE_MODEL_OUTPUT, type(payload).__name__,
                    "the compiler returned something that is not a JSON object. The graph is empty "
                    "and says so; nothing was invented in its place.")
        return _assemble(request, comp, receipt.model_copy(update={"parsed": False}),
                         compiler_kind="unavailable")

    for index, row in enumerate(_rows(payload, "claims")):
        comp.claim(index, row)
    comp.build_claims()

    live = {c.claim_id for c in comp.claims}
    by_id = {c.claim_id: c for c in comp.claims}

    def _claim_ref(ref: Any, where: str) -> Optional[str]:
        target = comp.by_ref.get(str(ref).strip())
        if target is None or target not in live:
            comp.refuse(CompilerRefusalKind.DANGLING_REFERENCE, str(ref),
                        "points at a claim that is not in this graph — either the compiler invented "
                        "the reference, or the claim it named was itself refused. Dropped: a "
                        "dangling reference renders as a supported claim in any UI that follows "
                        "edges.", detail=[where])
            return None
        return target

    # ── edges ──
    edges: List[ClaimEdge] = []
    seen_edges: Set[str] = set()
    for index, row in enumerate(_rows(payload, "edges")):
        where = f"edge {index}"
        raw_kind = _text(row.get("kind"))
        if raw_kind not in set(contracts.closed_set("claim_edge_kinds")):
            comp.refuse(CompilerRefusalKind.UNKNOWN_EDGE_KIND, raw_kind or "(empty)",
                        f"not one of {list(contracts.closed_set('claim_edge_kinds'))}. Dropped "
                        f"rather than read as `supports`: an unreadable rhetorical job silently "
                        f"turned into support is how an argument gains evidence nobody offered.",
                        detail=[where])
            continue
        source = _claim_ref(row.get("from") or row.get("from_claim"), where)
        target = _claim_ref(row.get("to") or row.get("to_claim"), where)
        if source is None or target is None or source == target:
            if source is not None and source == target:
                comp.refuse(CompilerRefusalKind.DANGLING_REFERENCE, source,
                            "an edge from a claim to itself. Dropped.", detail=[where])
            continue
        kind = ClaimEdgeKind(raw_kind)
        edge_id = ids.edge_id(comp.inquiry_id, kind, source, target)
        if edge_id in seen_edges:
            continue
        seen_edges.add(edge_id)
        edges.append(ClaimEdge(edge_id=edge_id, kind=kind, from_claim=source, to_claim=target,
                               why=_text(row.get("why"))))

    # ── observables ──
    observables: List[ObservableSpec] = []
    per_claim: Dict[str, int] = {}
    for index, row in enumerate(_rows(payload, "observables")):
        where = f"observable {index}"
        found = contracts.geometry_keys_in(row)
        if found:
            comp.refuse(CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                        "an observable REQUESTS a measurement; it may not carry one. Dropped.",
                        detail=[where])
            continue
        claim_id = _claim_ref(row.get("claim") or row.get("claim_ref"), where)
        if claim_id is None:
            continue
        kind_text = _text(row.get("kind")) or _text(row.get("observable_kind"))
        if not kind_text:
            continue
        classes = _enum_list(row.get("capability_classes"), CapabilityClass, "capability_classes",
                             CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS, where,
                             comp.inquiry_id, comp.refusals)
        if not classes:
            comp.refuse(CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS, kind_text[:120],
                        "the observable requested no capability class this system declares, so "
                        "there is nothing to broker and nothing to report as a gap. Dropped.",
                        detail=[where])
            continue
        claim = by_id[claim_id]
        if claim.claim_kind is ClaimKind.HISTORICAL_OR_SOURCED and \
                CapabilityClass.EXTERNAL_SOURCE not in classes:
            comp.refuse(CompilerRefusalKind.SOURCED_CLAIM_ASKED_OF_AN_ORGAN,
                        ", ".join(c.value for c in classes),
                        "a historical claim routed to an image capability. Its warrant is outside "
                        "the picture; asking an instrument for it would make an image measurement "
                        "of something the image cannot settle. Dropped rather than rewritten to "
                        "`external_source`, which would be the compiler inventing a request.",
                        detail=[where, claim.text[:120]])
            continue
        if per_claim.get(claim_id, 0) >= MAX_OBSERVABLES_PER_CLAIM:
            comp.notes.append(f"{where}: more than {MAX_OBSERVABLES_PER_CLAIM} observables were "
                              f"requested for one claim; the extras were not kept")
            continue

        targets = [str(t).strip() for t in row.get("targets") or () if str(t).strip()]
        observable_id = ids.observable_id(comp.inquiry_id, claim_id, kind_text, targets)
        if any(o.observable_id == observable_id for o in observables):
            continue
        grounds = _enum_list(row.get("ground_forms"), GroundForm, "ground_forms",
                             CompilerRefusalKind.UNKNOWN_GROUND_FORM, where,
                             comp.inquiry_id, comp.refusals)
        raw_scope = _text(row.get("image_scope"))
        observables.append(ObservableSpec(
            observable_id=observable_id, claim_id=claim_id, observable_kind=kind_text,
            targets=targets,
            image_scope=(ImageScope(raw_scope) if raw_scope in {s.value for s in ImageScope}
                         else claim.image_scope),
            capability_classes=classes, ground_forms=grounds,
            success_when=_text(row.get("success_when")),
            ambiguous_when=_text(row.get("ambiguous_when")),
            refused_when=_text(row.get("refused_when")),
            remains_interpretive=_text(row.get("remains_interpretive")),
            alternatives=_alternatives(comp, _rows(row, "alternatives"), observable_id, where),
            note=_text(row.get("note"))))
        per_claim[claim_id] = per_claim.get(claim_id, 0) + 1
        comp.observable_by_ref[_text(row.get("ref")) or f"#{index}"] = observable_id

    # ── decisions ──
    decisions: List[DecisionCandidate] = []
    for index, row in enumerate(_rows(payload, "decisions")):
        where = f"decision {index}"
        raw_kind = _text(row.get("kind"))
        if raw_kind not in {k.value for k in DecisionKind}:
            comp.refuse(CompilerRefusalKind.UNKNOWN_DECISION_KIND, raw_kind or "(empty)",
                        f"not one of {[k.value for k in DecisionKind]}; the decision candidate was "
                        f"dropped rather than filed under the nearest kind.", detail=[where])
            continue
        kind = DecisionKind(raw_kind)
        question = _text(row.get("question"))
        why_now = _text(row.get("why_now"))
        if not question or not why_now:
            comp.notes.append(f"{where}: a decision candidate without a question or a stated "
                              f"consequence was dropped. 'The system is uncertain' is not a reason "
                              f"to interrupt somebody.")
            continue
        decision_id = ids.decision_id(comp.inquiry_id, kind, question)
        options = _alternatives(comp, _rows(row, "options"), decision_id, where)
        if len(options) < 2 and kind is not DecisionKind.CONFIRM_AUTHOR_EXCLUSIVE_ACT:
            comp.notes.append(f"{where}: a fork with {len(options)} branch(es) was dropped. Asking "
                              f"about a choice that has one answer trains a person to click "
                              f"through.")
            continue
        # A DROPPED AFFECT REFERENCE IS RECORDED. A decision whose consequences point at nothing is
        # a question a person cannot act on, and the reference that failed to resolve is usually a
        # claim or observable that was itself refused — which is the fact worth surfacing.
        named = [str(r).strip() for r in row.get("affects") or () if str(r).strip()]
        affected: List[str] = []
        unresolved: List[str] = []
        for key in named:
            resolved = comp.by_ref.get(key) or comp.observable_by_ref.get(key)
            if not resolved:
                unresolved.append(key)
            elif resolved not in affected:
                affected.append(resolved)
        for key in unresolved:
            comp.refuse(CompilerRefusalKind.DANGLING_REFERENCE, key,
                        "a decision candidate named something it would change that is not in the "
                        "graph — usually a claim or observable that was itself refused.",
                        detail=[where])
        if named and not affected:
            comp.notes.append(f"{where}: every object this decision said it would change was "
                              f"refused, so the decision was dropped. A fork whose consequences "
                              f"point at nothing is a question nobody can act on.")
            continue
        decisions.append(DecisionCandidate(
            decision_id=decision_id, kind=kind, question=question, why_now=why_now,
            affected_refs=affected, options=options,
            allow_free_text=bool(row.get("allow_free_text", True)),
            blocking=bool(row.get("blocking"))))

    # ── semantic remainder ──
    measurable_subjects = {c.subject.strip().lower() for c in comp.claims
                           if c.epistemic_demand is DemandKind.MEASURABLE and c.subject.strip()}
    measurable_targets = {t.strip().lower() for o in observables for t in o.targets
                          if t.strip() and not set(o.capability_classes) <= NON_MEASURING_CLASSES}
    remainder: List[SemanticRemainderItem] = []
    seen_terms: Set[str] = set()
    for index, row in enumerate(_rows(payload, "semantic_remainder")):
        where = f"semantic remainder {index}"
        term = _text(row.get("term"))
        if not term or term.lower() in seen_terms:
            continue
        if term.lower() in measurable_subjects or term.lower() in measurable_targets:
            # Lane A's precedent exactly: the remainder entry is dropped and the demand stands.
            # Refusing here by name keeps the contradiction visible instead of turning the whole
            # compilation into a ValidationError somebody reads as a bug in the schema.
            comp.refuse(CompilerRefusalKind.REMAINDER_CLAIMED_MEASURABLE, term,
                        "the compiler called this both a semantic remainder and something a "
                        "measurement would reach. A remainder is what measurement does not reach; "
                        "the remainder entry was dropped and the measurable request stands.",
                        detail=[where])
            continue
        seen_terms.add(term.lower())
        classes = _enum_list(row.get("contributing_capability_classes"), CapabilityClass,
                             "capability_classes", CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS,
                             where, comp.inquiry_id, comp.refusals)
        refs = [r for r in (_claim_ref(x, where) for x in row.get("claims") or ()) if r]
        remainder.append(SemanticRemainderItem(
            term=term, why=_text(row.get("why"), "the compiler gave no reason"),
            contributing_capability_classes=classes, claim_refs=refs))

    # ── gaps stated rather than filled ──
    if comp.claims and not observables:
        comp.notes.append("the compiler produced claims and requested no observable. That may be "
                          "correct for a wholly interpretive prompt; it is stated rather than "
                          "filled in on the compiler's behalf.")
    interpretive = [c for c in comp.claims
                    if c.epistemic_demand in (DemandKind.INTERPRETIVE, DemandKind.IMAGINED)]
    if interpretive and not remainder:
        comp.notes.append("the compiler produced interpretive or imagined claims and no semantic "
                          "remainder. The gap is stated rather than filled in on its behalf.")
    plural = [o for o in observables if len(o.alternatives) >= 2]
    undecided = [o.observable_id for o in plural
                 if not any(o.observable_id in d.affected_refs for d in decisions)]
    if undecided:
        comp.notes.append(
            f"{len(undecided)} observable(s) offer more than one operationalization with no "
            f"decision candidate raised. That is the compiler's judgement that the choice is not "
            f"material; it is recorded rather than overridden here.")

    return _assemble(request, comp, receipt.model_copy(update={"parsed": True}),
                     compiler_kind=("replay" if receipt.call_topology is CallTopology.REPLAY
                                    else "model"),
                     edges=edges, observables=observables, decisions=decisions,
                     remainder=remainder)


def _assemble(request: CompilationRequest, comp: _Compilation, receipt: ModelReceipt, *,
              compiler_kind: str, edges: Sequence[ClaimEdge] = (),
              observables: Sequence[ObservableSpec] = (),
              decisions: Sequence[DecisionCandidate] = (),
              remainder: Sequence[SemanticRemainderItem] = ()) -> SemanticInquiryGraph:
    frame = dict(request.inquiry_frame or {})
    return SemanticInquiryGraph(
        graph_id=ids.graph_id(request.inquiry_id, request.prompt),
        inquiry_id=request.inquiry_id,
        prompt=request.prompt,                    # VERBATIM. Never rewritten or clarified.
        image_refs=list(request.images),
        inquiry_frame=frame,
        reading=request.reading,
        claims=comp.claims,
        claim_edges=list(edges),
        observables=list(observables),
        decision_candidates=list(decisions),
        semantic_remainder=list(remainder),
        refusals=comp.refusals,
        provenance=GraphProvenance(
            producer=PRODUCER, compiler_kind=compiler_kind,
            inquiry_frame_schema_version=str(frame.get("schema_version") or ""),
            theorist=request.reading.provenance if request.reading else None,
            compiler=receipt, prompt_sha256=sha256_of(request.prompt),
            compiled_at=request.now),
        notes=comp.notes)


# ── the replay implementation ────────────────────────────────────────────────

class FrozenSemanticCompiler:
    """Replays a frozen model payload through the production parser.

    The whole generality proof rests on this class containing no domain knowledge: two fixtures from
    unrelated subjects are two different JSON files handed to one code path.
    """

    name = "replay"

    def __init__(self, payload: Any, *, model: Optional[str] = None):
        self._payload = payload
        self._model = model

    def compile(self, request: CompilationRequest) -> SemanticInquiryGraph:
        receipt = ModelReceipt(
            role=ROLE, model=self._model,
            prompt_sha256=sha256_of(build_prompt(request)), requested_at=request.now,
            raw_response_sha256=[sha256_of(json.dumps(self._payload, sort_keys=True,
                                                      ensure_ascii=False))],
            call_count=0, call_topology=CallTopology.REPLAY,
            notes=["replayed from a frozen model output; no network call was made"])
        return _compile_payload(request, self._payload, receipt)


# ── the live implementation ──────────────────────────────────────────────────

class ModelSemanticCompiler:
    """One call, closed vocabulary, refusals kept, and no rule-based fallback anywhere."""

    name = "model"

    def __init__(self, client: Any = None, *, model: Optional[str] = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        self.calls: int = 0
        self.last_notes: Tuple[str, ...] = ()

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

    def compile(self, request: CompilationRequest) -> SemanticInquiryGraph:
        user_prompt = build_prompt(request)
        prompt_hash = sha256_of(user_prompt)
        if not self.is_available():
            return self._unavailable(
                request, prompt_hash,
                "the semantic compiler is unavailable (no client or API key)")
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
        except Exception as exc:
            return self._unavailable(request, prompt_hash,
                                     f"the semantic compiler failed: {type(exc).__name__}")
        self.last_notes = (f"compiler: {self.name}",)
        notes = [f"finish_reason: {finish or 'not reported'}"]
        if finish == "length":
            # A TRUNCATED GRAPH THAT STILL PARSES. The failure worth naming: a model that ran out
            # of budget and happened to close its JSON returns a thin decomposition that looks
            # exactly like an honest one. `finish_reason` is the only thing that tells them apart,
            # so it travels on the receipt whatever it says.
            notes.append("the compiler ran out of output budget. Whatever is in this graph is a "
                         "PREFIX of what it was writing, and a short graph here is not evidence "
                         "that the prompt decomposes into few claims.")
        receipt = ModelReceipt(role=ROLE, model=self.model, provider="groq",
                               prompt_sha256=prompt_hash, requested_at=request.now,
                               raw_response_sha256=[sha256_of(raw)], call_count=self.calls,
                               call_topology=CallTopology.TEXT_ONLY, notes=notes)
        return _compile_payload(request, payload, receipt)

    def _unavailable(self, request: CompilationRequest, prompt_hash: str,
                     why: str) -> SemanticInquiryGraph:
        """An empty graph that says the compiler was unavailable.

        NO rule-based fallback, and the omission is the design. `GroqArgumentPlanner` gives the
        argument one level down: nothing rule-based can decompose prose into claims, so a fallback
        would have to invent a decomposition — the single worst failure this module has.
        """
        self.last_notes = (f"compiler: {self.name}", why)
        comp = _Compilation(request)
        comp.refuse(CompilerRefusalKind.COMPILER_UNAVAILABLE, ROLE, why)
        comp.notes.append("the graph is empty because the compiler did not answer. Nothing "
                          "rule-based can atomize prose into claims, so nothing was invented in "
                          "its place.")
        receipt = ModelReceipt(role=ROLE, model=self.model, provider="groq",
                               prompt_sha256=prompt_hash, requested_at=request.now,
                               parsed=False, refusal=why, call_count=self.calls,
                               call_topology=CallTopology.UNAVAILABLE)
        return _assemble(request, comp, receipt, compiler_kind="unavailable")


def compile_graph(request: CompilationRequest, compiler: Optional[Any] = None
                  ) -> SemanticInquiryGraph:
    """Compile with the given compiler, defaulting to the live one. No network unless it is used."""
    return (compiler or ModelSemanticCompiler()).compile(request)


__all__ = ["ROLE", "PRODUCER", "MAX_CLAIMS", "MAX_OBSERVABLES_PER_CLAIM", "SYSTEM_PROMPT",
           "build_prompt", "FrozenSemanticCompiler", "ModelSemanticCompiler", "compile_graph"]
