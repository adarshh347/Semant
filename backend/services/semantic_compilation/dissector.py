"""
HARNESS-003A §4 — the semantic dissector: source units in, anchored atoms and dispositions out.

    source ledger (batched)
      -> atoms, each quoting the unit it came from
      -> one disposition per unit: represented / duplicate / remainder / refused

THE PASS THAT MUST NOT SUMMARISE. Everything else in the council can afford to be terse; this one
cannot, because it is the only pass that ever sees the source prose. A dissector that turns four
observations into one tidy sentence destroys material nothing downstream can recover, and the
coverage ledger would report `represented_by` with a straight face.

So the prompt asks for MORE atoms rather than better ones, the batches are small enough that the
budget cannot force brevity, and a batch that fails to mention one of its own inputs is
`coverage_failed` rather than a short success.

## What the dissector is not allowed to do

  · SEE. It receives the ledger as text. It is one further remove from the pixels than the theorist,
    and an atom anchored to a unit that does not contain it is the failure that follows from looking.
  · REATTRIBUTE. An atom drawn only from the person's clauses stays `author: user`, and this module
    sets that field itself rather than trusting the model's answer. The model is asked for the
    anchors; authorship is DERIVED from which units those anchors are, so a model that claims a
    person's hypothesis as its own observation is corrected by construction rather than by a rule it
    could get wrong.
  · INVENT AN ANCHOR. A `source_unit_id` outside the ledger is refused by name and the atom goes
    with it. The alternative — keeping the atom and dropping the anchor — is precisely an unanchored
    atom, which reads exactly like a found one.
  · OMIT. A unit the model does not mention at all is not silently remainder. Remainder is a
    JUDGEMENT with a reason; silence is an omission, and the two are different facts about the pass.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.semantic_compilation import (AtomAuthor, AtomKind, CompilerRefusal,
                                                  CompilerRefusalKind, CoverageDisposition,
                                                  DispositionKind, DissolutionPass, ImageScope,
                                                  PassOutcome, PassReceipt, SemanticAtom,
                                                  SourceUnit)

from . import contracts, ids, ledger as ledger_mod
from .base import refusal
from .passes import ModelPass, PassBudget, PassResult, batched, merge_receipts

ROLE = "semantic_dissector"
PRODUCER = "semantic_compilation/dissector-v1"

#: THREE units per call, and the budget left at 4096. Both numbers were learned the hard way.
#:
#: THE BATCH IS THE ONLY REAL LEVER, and the directive said so before the live run proved it. Six
#: rich reading blocks produce more atoms than 4096 tokens hold, so five of six batches truncated.
#: The obvious response — raise the budget to 8192 — made every call fail outright:
#:
#:     413: Request too large … tokens per minute (TPM): Limit 8000, Requested 9768
#:
#: A provider counts `max_completion_tokens` against the per-minute allowance whether or not the
#: model uses them, so a budget approaching that ceiling is a request that cannot be sent at all.
#: The budget is bounded from ABOVE by the account, not chosen from below by the pass — which is
#: exactly why "do not merely raise token limits" is the rule and shrinking the batch is the fix.
#:
#: Three units at 4096 leaves room for the prompt inside the same allowance, and a batch that small
#: has less to say than the budget holds — so a truncation here now means something is wrong rather
#: than that the input was large.
DEFAULT_BUDGET = PassBudget(max_completion_tokens=4096, batch_size=3)

#: A unit that produces more atoms than this is being paraphrased word by word rather than
#: dissolved. The overflow is REPORTED, never trimmed into looking correct.
MAX_ATOMS_PER_UNIT = 12

SYSTEM_PROMPT = (
    "You are a semantic dissector inside a visual close-reading tool. You are given SOURCE UNITS: "
    "clauses the person wrote, and blocks a vision model produced when it looked at their images. "
    "You do not see the images. You output JSON and nothing else.\n\n"
    "Your job is to break each source unit into the smallest units of meaning it actually "
    "contains, and to say what happened to every unit you were given.\n\n"
    "1. DO NOT SUMMARISE. You are the only stage that reads this prose. A source unit saying four "
    "things becomes four atoms. If you are unsure whether something is one unit of meaning or two, "
    "emit two.\n"
    "2. SEPARATE THE KINDS. A thing being present, how it looks, how two things stand to each "
    "other, a statement across several sources, a reading of what it means, an assertion whose "
    "warrant is outside the picture, an X-because-Y, and a proposal for something that does not "
    "exist are eight different kinds. Do not merge a quality into the thing that has it, and do "
    "not merge an effect into its cause: `it has sharp edges` and `that makes it read as hard` are "
    "two atoms, and only one of them could ever be observed.\n"
    "3. ANCHOR EVERY ATOM. Name the `source_unit_id`s it came from and quote the words, verbatim, "
    "from those units. An atom you cannot anchor does not belong in the output.\n"
    "4. ACCOUNT FOR WHAT YOU DID NOT DISSOLVE. A unit you emitted at least one atom for is "
    "accounted for by those atoms and needs no entry. For every OTHER unit — one you produced no "
    "atom for — give exactly one disposition:\n"
    "   `duplicate_of` — name the one other source unit that already says it;\n"
    "   `semantic_remainder` — it says something real that no atom captures; give the reason;\n"
    "   `refused` — you did not dissolve it; give the reason.\n"
    "   Leaving such a unit out is not an option and is not the same as remainder.\n"
    "5. KEEP OPEN WORDS. `subject`, `predicate` and `object` are free text in the source's own "
    "vocabulary. Do not translate them into a controlled term.\n\n"
    "Hard rules:\n"
    "- Never output a mask, box, point, polygon, coordinate, pixel count, region id or confidence. "
    "Nothing has been measured and you have not seen anything.\n"
    "- Never restate a person's hypothesis as an observation of your own. If it came from their "
    "clause, it is theirs.\n"
    "- Never invent a source_unit_id. Use only the ids you were given."
)


def build_prompt(units: Sequence[SourceUnit], *, prompt: str, batch: Sequence[SourceUnit]) -> str:
    """One batch's request. The whole prompt is shown as CONTEXT and the batch as the work.

    The person's full question is included because a clause read without it loses what it is a
    clause of — but only the batch's units carry ids, so an atom cannot be anchored to context.
    """
    vocabulary = {
        "atom_kinds": contracts.graph_contract()["atom_kinds"],
        "coverage_dispositions": contracts.graph_contract()["coverage_dispositions"],
        "image_scopes": list(contracts.closed_set("image_scopes")),
    }
    return (
        f"THE PERSON'S WHOLE QUESTION, for context only. You may not anchor an atom to this:\n"
        f"{prompt}\n\n"
        f"THE SOURCE UNITS TO DISSOLVE — emit atoms for these; any you emit no atom for "
        f"needs a disposition:\n"
        f"{json.dumps(ledger_mod.digest_for_prompt(batch), indent=2, ensure_ascii=False)}\n\n"
        f"THE VOCABULARY — use only these:\n{json.dumps(vocabulary, indent=2)}\n\n"
        f"Return JSON of exactly this shape. `ref` values are yours to invent and are used only to "
        f"link atoms to dispositions within this response:\n"
        f'{{"atoms": [{{"ref": "a1", "text": "<one unit of meaning>", '
        f'"unit_kind": "<atom kind>", "source_unit_ids": ["<an id from above>"], '
        f'"quotes": ["<the words, verbatim from that unit>"], '
        f'"subject": "", "predicate": "", "object": "", '
        f'"image_scope": "<image scope>", "note": ""}}], '
        f'"coverage": [{{"source_unit_id": "<an id you emitted NO atom for>", '
        f'"disposition": "<duplicate_of | semantic_remainder | refused>", '
        f'"refs": ["<a source unit id, for duplicate_of only>"], "reason": ""}}]}}\n'
        f"Emit atoms first. Every unit you produced no atom for must appear in `coverage`."
    )


class _Dissection:
    """One batch's parse. Local refs resolve to content-derived ids; every anchor is checked."""

    def __init__(self, inquiry_id: str, ledger: Sequence[SourceUnit]):
        self.inquiry_id = inquiry_id
        self.units = {u.source_unit_id: u for u in ledger}
        self.user_units = ledger_mod.user_unit_ids(ledger)
        self.atoms: List[SemanticAtom] = []
        self.coverage: List[CoverageDisposition] = []
        self.refusals: List[CompilerRefusal] = []
        self.by_ref: Dict[str, str] = {}

    def refuse(self, kind: CompilerRefusalKind, what: str, why: str,
               detail: Sequence[str] = ()) -> None:
        self.refusals.append(refusal(self.inquiry_id, kind, what, why, detail))

    # ── atoms ──

    def atom(self, index: int, row: Mapping[str, Any], batch: Set[str]) -> None:
        where = f"atom {index}"
        text = str(row.get("text") or "").strip()
        if not text:
            return

        raw_kind = str(row.get("unit_kind") or row.get("kind") or "").strip()
        if raw_kind not in set(contracts.closed_set("atom_kinds")):
            self.refuse(CompilerRefusalKind.UNKNOWN_ATOM_KIND, raw_kind or "(empty)",
                        f"not one of {list(contracts.closed_set('atom_kinds'))}. The atom was "
                        f"dropped rather than filed under `unknown`: `unknown` means the dissector "
                        f"could not type it, and using it here would hide an invented vocabulary "
                        f"inside a legitimate one.", detail=[where, text[:160]])
            return
        kind = AtomKind(raw_kind)

        named = [str(s).strip() for s in row.get("source_unit_ids") or () if str(s).strip()]
        anchors = [s for s in named if s in self.units]
        invented = [s for s in named if s not in self.units]
        for bad in invented:
            self.refuse(CompilerRefusalKind.ATOM_SOURCE_NOT_IN_LEDGER, bad,
                        "the dissector anchored an atom to a source unit that is not in the "
                        "ledger. The anchor is the only thing separating what it found from what "
                        "it wrote.", detail=[where, text[:120]])
        if not anchors:
            self.refuse(CompilerRefusalKind.UNANCHORED_ATOM, text[:120],
                        "an atom with no anchor in the ledger. It reads exactly like one that was "
                        "found, so it is dropped rather than kept with an empty pointer.",
                        detail=[where])
            return
        outside = [a for a in anchors if a not in batch]
        if outside:
            # Not a refusal: anchoring to a unit from an earlier batch is legitimate and useful —
            # a comparison genuinely spans them. It is recorded so a reader can see it happened.
            pass

        # AUTHORSHIP IS DERIVED, NEVER READ. A model that claimed the person's hypothesis as its own
        # observation would be corrected by a rule it could also get wrong; deriving it from which
        # units the anchors are makes the claim unrepresentable instead.
        author = (AtomAuthor.USER if anchors and all(a in self.user_units for a in anchors)
                  else AtomAuthor.SEMANTIC_DISSECTOR)
        claimed = str(row.get("author") or "").strip()
        if claimed and claimed != author.value:
            self.refuse(CompilerRefusalKind.USER_STATEMENT_REATTRIBUTED, claimed,
                        f"the dissector attributed this atom to {claimed!r}; its anchors make it "
                        f"{author.value!r}. Authorship is derived from the source units rather than "
                        f"taken, so the person's own hypothesis cannot be relabelled as a model "
                        f"observation.", detail=[where, text[:120]])

        scope_raw = str(row.get("image_scope") or "").strip()
        scope = (ImageScope(scope_raw) if scope_raw in {s.value for s in ImageScope}
                 else ImageScope.CORPUS)

        quotes = [str(q).strip() for q in row.get("quotes") or () if str(q).strip()]
        kept, missing = self._verified_quotes(quotes, anchors)
        images = sorted({r for a in anchors for r in self.units[a].image_refs})

        atom_id = ids.atom_id(self.inquiry_id, kind, text, anchors)
        if any(a.atom_id == atom_id for a in self.atoms):
            self.by_ref[str(row.get("ref") or f"#{index}")] = atom_id
            return
        self.by_ref[str(row.get("ref") or f"#{index}")] = atom_id
        self.atoms.append(SemanticAtom(
            atom_id=atom_id, text=text, unit_kind=kind, source_unit_ids=anchors, quotes=kept,
            subject=str(row.get("subject") or "").strip(),
            predicate=str(row.get("predicate") or "").strip(),
            object=str(row.get("object") or "").strip(),
            image_scope=scope, image_refs=images, author=author,
            note=str(row.get("note") or "").strip(),
            provenance={"producer": PRODUCER, "role": ROLE,
                        **({"quotes_not_found": missing} if missing else {}),
                        **({"spans_batches": True} if outside else {})}))

    def _verified_quotes(self, quotes: Sequence[str], anchors: Sequence[str]
                         ) -> Tuple[List[str], List[str]]:
        """Quotes that really appear in the units they are attributed to, and the ones that do not.

        A quote is KEPT either way — deleting it would hide that the dissector paraphrased — but a
        paraphrase is recorded on the atom's provenance so a UI never highlights it as verbatim.
        """
        haystacks = [ids.normalise(self.units[a].exact_quote) for a in anchors]
        kept: List[str] = []
        missing: List[str] = []
        for quote in quotes:
            kept.append(quote)
            if not any(ids.normalise(quote) in hay for hay in haystacks):
                missing.append(quote)
        return kept, missing

    # ── coverage ──

    def derive_representation(self, units: Sequence[SourceUnit], seen: Set[str]) -> None:
        """A unit with at least one atom anchored to it IS represented. Derived, never restated.

        THE LIVE RUN FORCED THIS, and it is a better rule than the one it replaces. Asking the model
        to list `represented_by` for every unit made it spend its completion budget restating ids it
        had already written on each atom — five of six batches ran out mid-`coverage`, so 121 real
        atoms arrived with zero dispositions and the audit reported the whole ledger uncovered.

        It is also stronger. Whether a unit has an atom is a FACT about the output, not an opinion
        about it, and a derived disposition cannot disagree with the anchors the way a restated one
        can. What still needs the model's judgement is the other case — a unit it produced no atom
        for is duplicate, remainder or refused, and only it can say which.

        A model that volunteers a `represented_by` anyway is harmless and ignored; one that calls a
        unit remainder while also emitting an atom for it is CONTRADICTING itself, and the atoms win
        with the contradiction recorded.
        """
        by_unit: Dict[str, List[str]] = {}
        for atom in self.atoms:
            for anchor in atom.source_unit_ids:
                by_unit.setdefault(anchor, []).append(atom.atom_id)

        for unit in units:
            refs = by_unit.get(unit.source_unit_id)
            if not refs:
                continue
            existing = next((c for c in self.coverage
                             if c.source_unit_id == unit.source_unit_id), None)
            if existing is not None:
                if existing.disposition is not DispositionKind.REPRESENTED_BY:
                    self.refuse(CompilerRefusalKind.SOURCE_UNIT_DOUBLE_COVERED,
                                unit.source_unit_id,
                                f"the dissector called this unit {existing.disposition.value!r} and "
                                f"also emitted {len(refs)} atom(s) anchored to it. The atoms are a "
                                f"fact about the output and the disposition is an opinion about it, "
                                f"so the atoms win and the contradiction is recorded.")
                    self.coverage.remove(existing)
                else:
                    continue
            self.coverage.append(CoverageDisposition(
                coverage_id=ids.coverage_id(self.inquiry_id, unit.source_unit_id),
                source_unit_id=unit.source_unit_id,
                disposition=DispositionKind.REPRESENTED_BY, refs=refs,
                reason="derived from the atoms anchored to this unit, not restated by the model"))
            seen.add(unit.source_unit_id)

    def disposition(self, index: int, row: Mapping[str, Any], batch: Set[str],
                    seen: Set[str]) -> None:
        where = f"coverage {index}"
        unit_id = str(row.get("source_unit_id") or "").strip()
        if unit_id not in self.units:
            self.refuse(CompilerRefusalKind.ATOM_SOURCE_NOT_IN_LEDGER, unit_id or "(empty)",
                        "a disposition for a source unit that is not in the ledger.", detail=[where])
            return
        if unit_id in seen:
            self.refuse(CompilerRefusalKind.SOURCE_UNIT_DOUBLE_COVERED, unit_id,
                        "the dissector disposed of one source unit twice. The first disposition "
                        "stands; two entries tell two stories about the same words.", detail=[where])
            return

        raw = str(row.get("disposition") or "").strip()
        if raw not in set(contracts.closed_set("coverage_dispositions")):
            self.refuse(CompilerRefusalKind.UNKNOWN_DISPOSITION, raw or "(empty)",
                        f"not one of {list(contracts.closed_set('coverage_dispositions'))}. The "
                        f"unit is left uncovered so the audit reports it, rather than being filed "
                        f"under a disposition nobody chose.", detail=[where])
            return
        disposition = DispositionKind(raw)
        reason = str(row.get("reason") or "").strip()
        refs = [str(r).strip() for r in row.get("refs") or () if str(r).strip()]

        if disposition is DispositionKind.REPRESENTED_BY:
            resolved = [self.by_ref.get(r, r) for r in refs]
            live = [r for r in resolved if any(a.atom_id == r for a in self.atoms)]
            if not live:
                # Represented by atoms that were all refused is not represented. Left uncovered so
                # the audit names it, which is the honest outcome rather than a silent downgrade.
                self.refuse(CompilerRefusalKind.SOURCE_UNIT_UNCOVERED, unit_id,
                            "the dissector said this unit was represented and named no atom that "
                            "survived. 'Represented by nothing' is the uncovered case wearing the "
                            "covered case's name.", detail=[where])
                return
            refs = live
        elif disposition is DispositionKind.DUPLICATE_OF:
            target = refs[0] if refs else ""
            if target not in self.units or target == unit_id:
                self.refuse(CompilerRefusalKind.DUPLICATE_POINTS_AT_ITSELF, target or "(empty)",
                            "a duplicate pointing at itself or at a unit that is not in the "
                            "ledger. It would remove the unit from the ledger while looking like "
                            "an entry in it.", detail=[where])
                return
            refs = [target]
        else:
            refs = []
            if not reason:
                reason = ("the dissector gave no reason. Recorded as stated rather than invented: "
                          "the reason is what separates an epistemic limit from a pass that failed.")

        seen.add(unit_id)
        self.coverage.append(CoverageDisposition(
            coverage_id=ids.coverage_id(self.inquiry_id, unit_id), source_unit_id=unit_id,
            disposition=disposition, refs=refs, reason=reason))


class SemanticDissector(ModelPass):
    """The role, batched over the ledger, with one receipt for the whole pass."""

    role = ROLE
    pass_name = DissolutionPass.SEMANTIC_DISSECTOR
    system_prompt = SYSTEM_PROMPT
    budget = DEFAULT_BUDGET

    def dissolve(self, units: Sequence[SourceUnit], *, prompt: str, inquiry_id: str,
                 attempt: int = 1) -> Tuple[List[SemanticAtom], List[CoverageDisposition],
                                            List[CompilerRefusal], PassReceipt]:
        comp = _Dissection(inquiry_id, units)
        receipts: List[PassReceipt] = []
        seen: Set[str] = set()

        # THE BATCH IS WHERE THE TIME GOES, so the batch is what a person watches. At three units a
        # call and roughly 1.5 calls a minute inside an 8000 TPM allowance, a 30-block reading is
        # eleven calls and several minutes — reported once at the end, that is a stage which sat
        # silent and then finished, which is indistinguishable from one that hung.
        batches = batched(units, self.budget.batch_size)
        for number, batch in enumerate(batches, 1):
            batch_ids = {u.source_unit_id for u in batch}
            self.observe(f"dissolving batch {number} of {len(batches)}",
                         index=number, total=len(batches), outcome="started",
                         refs=sorted(batch_ids),
                         detail=f"{len(batch)} source unit(s)")
            result = self.invoke(build_prompt(units, prompt=prompt, batch=batch),
                                 inquiry_id=inquiry_id, attempt=attempt, inputs=len(batch))
            self.observe(f"dissolving batch {number} of {len(batches)}",
                         index=number, total=len(batches),
                         outcome=result.receipt.outcome.value, refs=sorted(batch_ids),
                         detail=result.receipt.detail or f"{len(batch)} source unit(s)")
            receipts.append(result.receipt)
            comp.refusals.extend(result.refusals)
            if result.payload is None:
                continue
            rows = result.payload.get("atoms")
            for index, row in enumerate(rows if isinstance(rows, list) else []):
                if isinstance(row, Mapping):
                    comp.atom(index, row, batch_ids)
            rows = result.payload.get("coverage")
            for index, row in enumerate(rows if isinstance(rows, list) else []):
                if isinstance(row, Mapping):
                    comp.disposition(index, row, batch_ids, seen)

        comp.derive_representation(units, seen)
        self._report_overflow(comp)
        outcome, detail = self._outcome(units, comp, receipts, seen)
        receipt = merge_receipts(self.pass_name, receipts, inquiry_id=inquiry_id, outcome=outcome,
                                 attempt=attempt, outputs=len(comp.atoms), detail=detail)
        return comp.atoms, comp.coverage, comp.refusals, receipt

    def _report_overflow(self, comp: _Dissection) -> None:
        per_unit: Dict[str, int] = {}
        for atom in comp.atoms:
            for anchor in atom.source_unit_ids:
                per_unit[anchor] = per_unit.get(anchor, 0) + 1
        for unit_id, count in per_unit.items():
            if count > MAX_ATOMS_PER_UNIT:
                comp.refuse(CompilerRefusalKind.UNKNOWN_ATOM_KIND, unit_id,
                            f"{count} atoms were emitted for one source unit, which is a "
                            f"word-by-word paraphrase rather than a dissolution. Reported and kept: "
                            f"trimming it would make an over-eager pass look correct.")

    def _outcome(self, units: Sequence[SourceUnit], comp: _Dissection,
                 receipts: Sequence[PassReceipt], seen: Set[str]) -> Tuple[PassOutcome, str]:
        """The narrowing the parse cannot do for itself.

        Order matters. `unavailable` beats everything — nothing ran. Truncation beats coverage,
        because an uncovered unit under a length stop is explained by the length stop and calling it
        `coverage_failed` would send a reader looking for a prompt bug. Coverage beats `thin`.
        """
        uncovered = [u.source_unit_id for u in units if u.source_unit_id not in seen]
        if receipts and all(r.outcome is PassOutcome.UNAVAILABLE for r in receipts):
            return PassOutcome.UNAVAILABLE, "no batch reached the dissector"
        if any(r.truncated for r in receipts):
            return (PassOutcome.TRUNCATED,
                    f"{sum(1 for r in receipts if r.truncated)} of {len(receipts)} batch(es) hit "
                    f"the completion budget; {len(uncovered)} unit(s) uncovered as a result")
        if not comp.atoms:
            return PassOutcome.EMPTY, "the dissector produced no atom that survived anchoring"
        if uncovered:
            for unit_id in uncovered:
                comp.refuse(CompilerRefusalKind.SOURCE_UNIT_UNCOVERED, unit_id,
                            "the dissector never mentioned this source unit. Silence is an "
                            "omission, not a remainder: remainder is a judgement with a reason.")
            return (PassOutcome.COVERAGE_FAILED,
                    f"{len(uncovered)} of {len(units)} source unit(s) received no disposition")
        return PassOutcome.COMPLETED, f"{len(comp.atoms)} atom(s) over {len(units)} source unit(s)"


class FrozenSemanticDissector(SemanticDissector):
    """A frozen dissector: the same parse, the same laws, a list of payloads instead of a provider."""

    def __init__(self, payloads: Sequence[Any], *, model: Optional[str] = None):
        super().__init__(client=None, model=model)
        self._frozen = list(payloads)
        self._served = 0

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1,
               inputs: int = 0) -> PassResult:
        from .passes import FrozenPass
        pass_through = FrozenPass(self._frozen[self._served:self._served + 1], model=self._model)
        pass_through.role = self.role
        pass_through.pass_name = self.pass_name
        self._served += 1
        self.calls += 1
        return pass_through.invoke(user_prompt, inquiry_id=inquiry_id, attempt=attempt,
                                   inputs=inputs)


__all__ = ["ROLE", "PRODUCER", "DEFAULT_BUDGET", "MAX_ATOMS_PER_UNIT", "SYSTEM_PROMPT",
           "build_prompt", "SemanticDissector", "FrozenSemanticDissector"]
