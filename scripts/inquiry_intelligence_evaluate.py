#!/usr/bin/env python3
"""
INTELLIGENCE-001B — did information flow, stay traceable, and become a comparison?

RESEARCH-ONLY. This module reads a finished inquiry session and produces structural counts. It
imports nothing from the inquiry services and changes nothing about them; a session record is the
only input, so an export, a replay and a live run are all evaluable by the same code.

## The one rule the whole file is built around

    zero  — the flow did the thing zero times
    null  — nothing in the record could say whether it did

`Measurement.value = None` is always accompanied by `refused`, a sentence saying what was missing.
This is `perception_lab_form_scoring`'s discipline and it is here for the same reason: a harness
that emits `0` for "there is no critique record at all" and `0` for "every relation was reviewed
and none accepted" has destroyed the only difference that mattered, and the number it prints is
believed either way.

## What it will not do

It does not score aesthetic quality or philosophical depth, and it does not proxy them. Those
questions are carried through from each case's `manual_review_questions` into every report,
alongside the `forbidden_shortcuts` whose `detected_by` is the literal string `none` — the
shortcuts that are real, matter, and are caught by nothing here. Printing that list in every
report is the point: it keeps the gap between what is checked and what counts in view.

## The two outcomes are separate fields

`workflow_outcome` is what the machinery says happened. `semantic_outcome` is what the record
shows was learned. The baseline fixture is the argument for the split — it closed `complete`,
saying "the chain closed: every claim carries a verdict", over a truncated compiler, a truncated
relation architect, a failed coverage audit, twenty claims and zero relations. One field would have
had to pick one of those, and it would have picked the reassuring one.

## Traceability runs through source spans, not through `image_scope`

A production claim carries NO `image_refs`. Its `image_scope` is a scope CLASS — `one_image`,
`corpus`, `image_pair`, `not_an_image_question` — and reading it as a list of post ids is a live
bug elsewhere in this tree (`--report-contradictions` prints the list). The only real path from a
claim to a picture is:

    claim.source_spans[].source_id  ->  reading block id  ->  block.image_refs  ->  post ids

which is what `_claim_images` walks, and why a claim sourced only from `prompt` is untraceable to
any image by construction rather than by accident.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

EVALUATION_VERSION = "inquiry-intelligence-evaluation.v1"

ROOT = Path(__file__).resolve().parents[1]
REHEARSALS = ROOT / "research" / "rehearsals" / "inquiry-intelligence"
CASES_DIR = REHEARSALS / "cases"
FIXTURES_DIR = REHEARSALS / "fixtures"
RUNS_DIR = REHEARSALS / "run-archive"

#: `complicates` and `challenges` are the contrast relations. `supports` is agreement,
#: `composes_from` and `generalizes` are constructions — none of the three is a contrast, and
#: counting them as one would let a run that agreed with itself everywhere score as comparative.
CONTRAST_KINDS = frozenset({"complicates", "challenges"})

#: Contract facts this evaluator had to discover from a real payload rather than from a schema,
#: each of which something in the tree currently gets wrong. Printed by `--report-contradictions`
#: so they travel with the harness instead of living only in a review comment.
CONTRACT_CONTRADICTIONS = (
    ("image_scope is a scope class, not a list of post ids",
     "`semantic_atoms[].image_scope` and `claims[].image_scope` carry one of "
     "`one_image` / `image_pair` / `corpus` / `not_an_image_question`. Post ids live in "
     "`image_refs`, which claims do not have at all. Anything indexing images by `image_scope` "
     "files every atom and claim under a post id that does not exist."),
    ("a claim carries no image reference of its own",
     "The only path from a claim to a picture is "
     "`source_spans[].source_id -> reading block -> block.image_refs`. A claim whose spans all "
     "have origin `prompt` is untraceable to any image by construction."),
    ("`image_ref` on the catalogue is a URL",
     "`corpus.image_refs_for` sets `image_ref` to the post's url, so `image_ref == image_url` on "
     "a real payload while citations elsewhere are post ids."),
    ("there is no relation-critique record",
     "Nothing in a session says whether a relation was reviewed, revised or rejected. Accept / "
     "revise / reject counts are therefore refused rather than reported as zero."),
)

#: Scope CLASSES, not post ids. Present so `_looks_like_a_post_id` can say why it rejected one.
SCOPE_CLASSES = frozenset({"one_image", "image_pair", "corpus", "not_an_image_question", ""})

#: Statuses that assert something was observed. The production `ClaimStatus` enum cannot express
#: these at all — which is the point: if one appears in a record, it arrived from somewhere that
#: does not go through the enum, and that is worth a finding rather than a shrug.
MEASURED_STATUSES = frozenset({"measured", "visible"})

UNDERPERFORMING_PASS_OUTCOMES = frozenset(
    {"thin", "truncated", "coverage_failed", "empty", "refused", "unavailable", "error"})
TRUNCATED_OUTCOMES = frozenset({"truncated"})
THIN_OUTCOMES = frozenset({"thin", "coverage_failed"})

#: Ordinary English. NO TOPIC WORDS: this list must stay usable on a corpus of anything, and a
#: stopword list that had learned this lane's subject matter would quietly tune the overlap ratio
#: to one rehearsal's vocabulary.
STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below
between both but by can cannot could did do does doing down during each few for from further had
has have having he her here hers herself him himself his how i if in into is it its itself me more
most my myself no nor not of off on once only or other ought our ours ourselves out over own same
she should so some such than that the their theirs them themselves then there these they this those
through to too under until up very was we were what when where which while who whom why with would
you your yours yourself yourselves it's i'm don't isn't aren't wasn't weren't okay btw shows show
different things turn turns make makes made rather assuming advance build determine explain propose
find these those combine merely without whether require
""".split())

WORD = re.compile(r"[a-z][a-z'-]{2,}")

#: Sentences that assert an instrument RAN. Deliberately narrow and deliberately about invocation
#: rather than about measurement: the baseline's composer set `measured_anything=false` honestly and
#: then wrote "one capability was invoked" in its own preamble, with zero receipts behind it. The
#: structured flag and the prose disagreed, and only one of them is what a person reads.
CAPABILITY_ASSERTIONS = (
    re.compile(r"\b(?:capabilit(?:y|ies))\b[^.]{0,40}\b(?:was|were|is|are)\s+"
               r"(?:invoked|run|executed|commissioned|called)", re.I),
    re.compile(r"\b(?:we|it|the run|the system)\s+(?:invoked|ran|executed|commissioned)\b"
               r"[^.]{0,40}\bcapabilit", re.I),
    re.compile(r"\b(?:one|two|three|\d+)\s+capabilit(?:y|ies)\b[^.]{0,30}"
               r"\b(?:invoked|run|executed|commissioned)", re.I),
)


# ── measurements ────────────────────────────────────────────────────────────

@dataclass
class Measurement:
    """A number, a refusal, or a number with a warning attached to it."""
    value: Any
    kind: str  # count | ratio | flag | breakdown | label
    refused: Optional[str] = None
    warning: Optional[str] = None
    detail: Any = None

    def __post_init__(self) -> None:
        if self.value is None and not self.refused:
            raise ValueError(
                "a null measurement must say what was missing. A silent null is the zero this "
                "module exists to avoid, wearing a different type.")
        if self.value is not None and self.refused:
            raise ValueError("a measurement cannot both have a value and refuse to produce one.")

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"value": self.value, "kind": self.kind}
        if self.refused:
            out["refused"] = self.refused
        if self.warning:
            out["warning"] = self.warning
        if self.detail is not None:
            out["detail"] = self.detail
        return out


def count(n: int, **kw: Any) -> Measurement:
    return Measurement(value=int(n), kind="count", **kw)


def ratio(n: Optional[float], **kw: Any) -> Measurement:
    return Measurement(value=None if n is None else float(n), kind="ratio", **kw)


def flag(b: Optional[bool], **kw: Any) -> Measurement:
    return Measurement(value=b, kind="flag", **kw)


def refuse(kind: str, why: str, **kw: Any) -> Measurement:
    return Measurement(value=None, kind=kind, refused=why, **kw)


# ── reading a session without trusting its shape ────────────────────────────

def _d(o: Any) -> Dict[str, Any]:
    return o if isinstance(o, dict) else {}


def _l(o: Any) -> List[Any]:
    return list(o) if isinstance(o, list) else []


def _s(o: Any) -> str:
    return o if isinstance(o, str) else ("" if o is None else str(o))


class Session:
    """A read-only view over a session export.

    Every accessor tolerates a missing branch and returns an empty one, because the records this
    reads include exports from older schema versions and half-finished runs. What it never does is
    invent a default that could be mistaken for data — an absent `posts` list is `[]` and the
    metrics that depend on it REFUSE rather than reporting zero images.
    """

    def __init__(self, raw: Mapping[str, Any]):
        self.raw = _d(raw)

    # top level
    @property
    def session_id(self) -> str: return _s(self.raw.get("session_id"))
    @property
    def inquiry_id(self) -> str: return _s(self.raw.get("inquiry_id"))
    @property
    def revision(self) -> Optional[int]:
        v = self.raw.get("revision")
        return v if isinstance(v, int) else None
    @property
    def schema_version(self) -> str: return _s(self.raw.get("schema_version"))
    @property
    def state(self) -> str: return _s(self.raw.get("state"))
    @property
    def stop_reason(self) -> str: return _s(self.raw.get("stop_reason"))
    @property
    def prompt(self) -> str: return _s(self.raw.get("prompt")) or _s(self.graph.get("prompt"))
    @property
    def posts(self) -> List[Dict[str, Any]]: return [_d(p) for p in _l(self.raw.get("posts"))]
    @property
    def stages(self) -> List[Dict[str, Any]]: return [_d(s) for s in _l(self.raw.get("stages"))]
    @property
    def verdicts(self) -> List[Dict[str, Any]]: return [_d(v) for v in _l(self.raw.get("verdicts"))]
    @property
    def synthesis(self) -> Dict[str, Any]: return _d(self.raw.get("synthesis"))
    @property
    def capability_receipts(self) -> List[Dict[str, Any]]:
        return [_d(r) for r in _l(self.raw.get("capability_receipts"))]
    @property
    def evidence(self) -> List[Dict[str, Any]]: return [_d(e) for e in _l(self.raw.get("evidence"))]
    @property
    def deployment(self) -> Dict[str, Any]: return _d(self.raw.get("deployment"))
    @property
    def provenance(self) -> Dict[str, Any]: return _d(self.raw.get("provenance"))

    # graph
    @property
    def graph(self) -> Dict[str, Any]: return _d(self.raw.get("graph"))
    @property
    def reading(self) -> Dict[str, Any]: return _d(self.graph.get("reading"))
    @property
    def blocks(self) -> List[Dict[str, Any]]: return [_d(b) for b in _l(self.reading.get("blocks"))]
    @property
    def source_units(self) -> List[Dict[str, Any]]:
        return [_d(u) for u in _l(self.graph.get("source_units"))]
    @property
    def atoms(self) -> List[Dict[str, Any]]:
        return [_d(a) for a in _l(self.graph.get("semantic_atoms"))]
    @property
    def claims(self) -> List[Dict[str, Any]]: return [_d(c) for c in _l(self.graph.get("claims"))]
    @property
    def edges(self) -> List[Dict[str, Any]]:
        return [_d(e) for e in _l(self.graph.get("claim_edges"))]
    @property
    def observables(self) -> List[Dict[str, Any]]:
        return [_d(o) for o in _l(self.graph.get("observables"))]
    @property
    def remainder(self) -> List[Dict[str, Any]]:
        return [_d(r) for r in _l(self.graph.get("semantic_remainder"))]
    @property
    def refusals(self) -> List[Dict[str, Any]]:
        return [_d(r) for r in _l(self.graph.get("refusals"))] + \
               [_d(r) for r in _l(self.raw.get("refusals"))]
    @property
    def passes(self) -> List[Dict[str, Any]]: return [_d(p) for p in _l(self.graph.get("passes"))]
    @property
    def gaps(self) -> List[Any]: return _l(self.raw.get("gaps"))
    @property
    def execution_scope(self) -> Dict[str, Any]:
        return _d(self.raw.get("execution_scope")) or _d(self.graph.get("execution_scope"))

    # ── derived, and the derivations that matter ────────────────────────────

    def declared_post_ids(self) -> List[str]:
        """The corpus, taken from the catalogue and the read ledger together.

        Both are consulted because they can disagree, and an image the theorist was handed but the
        read ledger never mentions is exactly the kind of thing this harness should not smooth over.
        """
        ids: List[str] = []
        for entry in _l(self.graph.get("image_refs")):
            pid = _s(_d(entry).get("post_id"))
            if pid and pid not in ids:
                ids.append(pid)
        for p in self.posts:
            pid = _s(p.get("post_id"))
            if pid and pid not in ids:
                ids.append(pid)
        return ids

    def block_images(self) -> Dict[str, List[str]]:
        """block_id -> post ids it declared. The only place post ids are read off the reading."""
        return {_s(b.get("block_id")): [_s(r) for r in _l(b.get("image_refs")) if _s(r)]
                for b in self.blocks}

    def _claim_images(self, claim: Mapping[str, Any]) -> List[str]:
        """Post ids a claim can be traced to — through its source spans, never through scope.

        `image_scope` is deliberately not consulted. It carries scope CLASSES, and a claim scoped
        `one_image` has not told anybody WHICH image; treating that token as a post id is how a
        panel elsewhere in this tree indexes every claim under a picture that does not exist.
        """
        by_block = self.block_images()
        out: List[str] = []
        spans = _l(claim.get("source_spans")) or ([claim["source_span"]]
                                                  if _d(claim.get("source_span")) else [])
        for span in spans:
            sid = _s(_d(span).get("source_id"))
            for pid in by_block.get(sid, []):
                if pid not in out:
                    out.append(pid)
        return out

    def claim_origins(self, claim: Mapping[str, Any]) -> List[str]:
        spans = _l(claim.get("source_spans")) or ([claim["source_span"]]
                                                  if _d(claim.get("source_span")) else [])
        return [_s(_d(s).get("origin")) for s in spans]

    def claim_by_id(self) -> Dict[str, Dict[str, Any]]:
        return {_s(c.get("claim_id")): c for c in self.claims}


def _looks_like_a_post_id(token: str) -> bool:
    """A scope class is not a post id, and neither is an empty string."""
    return bool(token) and token not in SCOPE_CLASSES


def _content_words(text: str) -> List[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]


# ── the metrics ─────────────────────────────────────────────────────────────
#
# Each takes a Session and returns a Measurement. The registry below is the public surface: a case
# expectation naming a metric that is not in it is reported as `unknown_metric` rather than passing
# silently, so a manifest cannot claim a check nobody implements.

def m_prompt_hypothesis_atoms(s: Session) -> Measurement:
    if not s.atoms:
        return refuse("count", "the graph carries no semantic atoms, so nothing can be attributed "
                               "to the person or to the images.")
    users = [a for a in s.atoms if _s(a.get("author")) == "user"]
    return count(len(users), detail={"atom_ids": [_s(a.get("atom_id")) for a in users][:40]})


def m_image_observation_atoms(s: Session) -> Measurement:
    if not s.atoms:
        return refuse("count", "the graph carries no semantic atoms.")
    obs = [a for a in s.atoms
           if _s(a.get("author")) != "user"
           and any(_looks_like_a_post_id(_s(r)) for r in _l(a.get("image_refs")))]
    return count(len(obs))


def m_prompt_hypotheses_preserved(s: Session) -> Measurement:
    """Is the person's own vocabulary still attributable to the person?

    Two ways this fails, and they are different failures:

      1. Nothing is attributed to the user at all, though the prompt asserted things — the person's
         claims have been absorbed into the model's voice.
      2. Something IS attributed to the user, but a claim quoting the prompt is authored by a model
         and carries no prompt origin — the assertion has been laundered into a finding.

    The check is deliberately not "count > 0". A prompt that asserts nothing (case 2 is close to
    one) should not be failed for producing no user atoms, so a prompt with no assertive content
    REFUSES rather than failing.
    """
    if not s.atoms and not s.claims:
        return refuse("flag", "the graph carries neither atoms nor claims; there is nothing whose "
                              "attribution could be checked.")
    prompt_units = [u for u in s.source_units if _s(u.get("source_type")) == "prompt_clause"
                    or _s(u.get("kind")) == "prompt_clause"]
    if not prompt_units:
        return refuse("flag", "no prompt clause reached the source ledger, so the prompt was never "
                              "represented as something that COULD be attributed.")

    user_atoms = [a for a in s.atoms if _s(a.get("author")) == "user"]
    mislabelled = [_s(u.get("source_unit_id")) for u in prompt_units
                   if _s(u.get("author")) not in ("user", "")]
    detail = {
        "prompt_source_units": [_s(u.get("source_unit_id")) for u in prompt_units],
        "user_authored_atoms": len(user_atoms),
        "prompt_units_not_attributed_to_the_person": mislabelled,
    }
    if mislabelled:
        return flag(False, detail=detail)
    return flag(bool(user_atoms), detail=detail)


def m_observations_total(s: Session) -> Measurement:
    if not s.reading:
        return refuse("count", "the graph carries no reading, so no observation was recorded.")
    if not s.blocks:
        return refuse("count", "the reading carries no blocks — it may be prose the producer never "
                               "split, which is not the same as a reading that observed nothing.")
    return count(len(s.blocks))


def m_observations_per_image(s: Session) -> Measurement:
    if not s.blocks:
        return refuse("breakdown", "the reading carries no blocks.")
    declared = s.declared_post_ids()
    if not declared:
        return refuse("breakdown", "no post id reached the session, so per-image counts have no "
                                   "denominator.")
    per = {pid: 0 for pid in declared}
    for refs in s.block_images().values():
        for pid in refs:
            per[pid] = per.get(pid, 0) + 1
    return Measurement(value=per, kind="breakdown")


def m_observations_per_image_min(s: Session) -> Measurement:
    per = m_observations_per_image(s)
    if per.value is None:
        return refuse("count", per.refused or "per-image counts unavailable.")
    return count(min(per.value.values()) if per.value else 0, detail=per.value)


def m_observations_with_image_refs(s: Session) -> Measurement:
    if not s.blocks:
        return refuse("count", "the reading carries no blocks.")
    n = sum(1 for refs in s.block_images().values()
            if any(_looks_like_a_post_id(r) for r in refs))
    return count(n)


def m_observations_without_image_refs(s: Session) -> Measurement:
    if not s.blocks:
        return refuse("count", "the reading carries no blocks.")
    missing = [bid for bid, refs in s.block_images().items()
               if not any(_looks_like_a_post_id(r) for r in refs)]
    return count(len(missing), detail={"block_ids": missing[:40]})


def m_image_diversity_images_cited(s: Session) -> Measurement:
    if not s.blocks:
        return refuse("count", "the reading carries no blocks.")
    cited = {r for refs in s.block_images().values() for r in refs if _looks_like_a_post_id(r)}
    return count(len(cited), detail={"post_ids": sorted(cited)})


def m_image_diversity_balance(s: Session) -> Measurement:
    """How evenly the reading spread itself, as least-attended share ÷ even share.

    1.0 is perfectly even; 0.0 means an image the run was given was never mentioned. It is a
    RATIO and not a verdict — an uneven reading of an uneven set of pictures is not a defect, and
    the number is here to be looked at next to `observations_per_image`, not thresholded alone.
    """
    per = m_observations_per_image(s)
    if per.value is None:
        return refuse("ratio", per.refused or "per-image counts unavailable.")
    counts = list(per.value.values())
    total = sum(counts)
    if not counts or total == 0:
        return refuse("ratio", "no block named any image, so there is no distribution to describe.")
    even = total / len(counts)
    return ratio(min(counts) / even, detail=per.value)


def m_lexical_prompt_copy_ratio(s: Session) -> Measurement:
    """How much of the reading's vocabulary was already in the prompt.

    A WARNING AND NEVER A FINDING. When a person names things that are actually in the pictures,
    a good reading SHOULD echo them — high overlap is as consistent with attentive looking as with
    parroting, and the two are told apart by reading the text, which is a manual question. What
    this number is for is deciding which runs to read first.
    """
    prompt_words = set(_content_words(s.prompt))
    if not prompt_words:
        return refuse("ratio", "the prompt carries no content words to overlap with.")
    body = " ".join(_s(b.get("text")) for b in s.blocks)
    words = _content_words(body)
    if not words:
        return refuse("ratio", "the reading carries no text to compare against the prompt.")
    hits = sum(1 for w in words if w in prompt_words)
    r = hits / len(words)
    warn = None
    if r >= 0.35:
        warn = (f"{r:.0%} of the reading's content words are already in the prompt. This is a "
                f"reason to read the run, not a finding: a reading that names what the person "
                f"named may be looking at the same real things.")
    return ratio(r, warning=warn,
                 detail={"reading_content_words": len(words), "in_prompt": hits})


def m_claims_total(s: Session) -> Measurement:
    return count(len(s.claims))


def m_claims_sourced_only_from_prompt(s: Session) -> Measurement:
    if not s.claims:
        return refuse("count", "the graph carries no claims.")
    hits = []
    for c in s.claims:
        origins = [o for o in s.claim_origins(c) if o]
        if origins and all(o == "prompt" for o in origins):
            hits.append(_s(c.get("claim_id")))
    return count(len(hits), detail={"claim_ids": hits[:40], "of_total": len(s.claims)})


def m_claims_with_image_traceability(s: Session) -> Measurement:
    if not s.claims:
        return refuse("count", "the graph carries no claims.")
    traceable = [_s(c.get("claim_id")) for c in s.claims if s._claim_images(c)]
    return count(len(traceable),
                 detail={"claim_ids": traceable[:40], "of_total": len(s.claims),
                         "path": "claim.source_spans[].source_id -> block.image_refs"})


def m_relation_count(s: Session) -> Measurement:
    return count(len(s.edges))


def _edge_is_cross_image(s: Session, edge: Mapping[str, Any]) -> Optional[bool]:
    by_id = s.claim_by_id()
    a, b = by_id.get(_s(edge.get("from_claim"))), by_id.get(_s(edge.get("to_claim")))
    if a is None or b is None:
        return None  # dangling — cannot be judged, must not be counted either way
    ia, ib = set(s._claim_images(a)), set(s._claim_images(b))
    if not ia or not ib:
        return None
    return bool(ia ^ ib)


def m_cross_image_relation_count(s: Session) -> Measurement:
    if not s.edges:
        return count(0, detail={"note": "no relation was produced, so none is cross-image."})
    verdicts = [_edge_is_cross_image(s, e) for e in s.edges]
    known = [v for v in verdicts if v is not None]
    if not known:
        return refuse("count",
                      "no relation could be placed against images: every endpoint either does not "
                      "resolve to a claim in this graph or resolves to a claim with no traceable "
                      "image. Zero here would read as 'all relations were within one image'.")
    return count(sum(1 for v in known if v),
                 detail={"judged": len(known), "unjudgeable": len(verdicts) - len(known)})


def m_contrast_count(s: Session) -> Measurement:
    if not s.edges:
        return count(0)
    return count(sum(1 for e in s.edges if _s(e.get("kind")) in CONTRAST_KINDS))


def m_cross_image_contrast_count(s: Session) -> Measurement:
    contrasts = [e for e in s.edges if _s(e.get("kind")) in CONTRAST_KINDS]
    if not contrasts:
        return count(0, detail={"note": "no contrast relation was produced."})
    verdicts = [_edge_is_cross_image(s, e) for e in contrasts]
    known = [v for v in verdicts if v is not None]
    if not known:
        return refuse("count", "no contrast relation could be placed against images.")
    return count(sum(1 for v in known if v))


def m_relation_source_completeness(s: Session) -> Measurement:
    """The share of relations whose BOTH endpoints resolve to claims in this graph.

    Refuses on an empty set rather than returning 1.0. A run with no relations is not a run whose
    relations were all well-formed, and 1.0 is the most flattering number in the file.
    """
    if not s.edges:
        return refuse("ratio", "no relation was produced, so completeness is undefined. A run with "
                               "no relations has not achieved perfect relation hygiene.")
    by_id = s.claim_by_id()
    ok = [e for e in s.edges
          if _s(e.get("from_claim")) in by_id and _s(e.get("to_claim")) in by_id]
    dangling = [_s(e.get("edge_id")) for e in s.edges if e not in ok]
    return ratio(len(ok) / len(s.edges), detail={"dangling_edge_ids": dangling[:40]})


def _critique_records(s: Session) -> List[Dict[str, Any]]:
    """Any record that reviews a RELATION. There is no such structure in the contract today."""
    out: List[Dict[str, Any]] = []
    for r in _l(s.graph.get("relation_critiques")) + _l(s.raw.get("relation_critiques")):
        out.append(_d(r))
    return out


_NO_CRITIC = ("the contract carries no relation-critique record. Nothing in a session distinguishes "
              "a relation that was reviewed and kept from one nobody looked at, so accept / revise "
              "/ reject cannot be counted. This is a gap in the pipeline, not in the run.")


def m_critic_accepted(s: Session) -> Measurement:
    recs = _critique_records(s)
    if not recs:
        return refuse("count", _NO_CRITIC)
    return count(sum(1 for r in recs if _s(r.get("outcome")) == "accepted"))


def m_critic_revised(s: Session) -> Measurement:
    recs = _critique_records(s)
    if not recs:
        return refuse("count", _NO_CRITIC)
    return count(sum(1 for r in recs if _s(r.get("outcome")) == "revised"))


def m_critic_rejected(s: Session) -> Measurement:
    recs = _critique_records(s)
    if not recs:
        return refuse("count", _NO_CRITIC)
    return count(sum(1 for r in recs if _s(r.get("outcome")) == "rejected"))


def m_relations_accepted_without_critique(s: Session) -> Measurement:
    if not s.edges:
        return count(0, detail={"note": "no relation was produced."})
    recs = _critique_records(s)
    if not recs:
        return refuse("count",
                      "every relation in this record is uncritiqued, but so is every relation in "
                      "every record: " + _NO_CRITIC + " Reporting "
                      f"{len(s.edges)} here would blame the run for a missing contract.")
    reviewed = {_s(r.get("relation_ref")) for r in recs}
    return count(sum(1 for e in s.edges if _s(e.get("edge_id")) not in reviewed))


def m_truncated_stages(s: Session) -> Measurement:
    named = [f"{_s(x.get('stage') or x.get('pass_name'))}"
             for x in (s.stages + s.passes) if _s(x.get("outcome")) in TRUNCATED_OUTCOMES]
    return count(len(named), detail={"stages": named})


def m_thin_stages(s: Session) -> Measurement:
    named = [f"{_s(x.get('stage') or x.get('pass_name'))}:{_s(x.get('outcome'))}"
             for x in (s.stages + s.passes) if _s(x.get("outcome")) in THIN_OUTCOMES]
    return count(len(named), detail={"stages": named})


def _scope_int(s: Session, key: str) -> Optional[int]:
    v = s.execution_scope.get(key)
    return v if isinstance(v, int) else None


def m_unexamined_atoms(s: Session) -> Measurement:
    v = _scope_int(s, "atoms_not_investigated")
    if v is None:
        return refuse("count", "the run declared no execution scope, so nothing states how many "
                               "atoms were left uninvestigated.")
    return count(v)


def m_unexamined_claims(s: Session) -> Measurement:
    v = _scope_int(s, "claims_not_investigated")
    if v is None:
        return refuse("count", "the run declared no execution scope.")
    return count(v)


def m_unexamined_relation_batches(s: Session) -> Measurement:
    allowed = _scope_int(s, "relation_batches_allowed")
    sent = _scope_int(s, "relation_batches_sent")
    if allowed is None or sent is None:
        return refuse("count", "the run did not declare both a relation-batch allowance and a "
                               "count of batches sent, so the shortfall cannot be computed. It is "
                               "not zero — it is unknown.")
    return count(max(0, allowed - sent), detail={"allowed": allowed, "sent": sent})


def m_observables_proposed(s: Session) -> Measurement:
    return count(len(s.observables))


def m_capability_gaps(s: Session) -> Measurement:
    gaps = [g for g in s.gaps]
    coded = [r for r in s.refusals if "capabilit" in _s(r.get("reason")).lower()
             or "capabilit" in _s(r.get("kind")).lower()]
    return count(len(gaps) + len(coded),
                 detail={"gaps": gaps[:20], "refusal_ids": [_s(r.get("refusal_id")) for r in coded]})


def m_capability_receipts(s: Session) -> Measurement:
    return count(len(s.capability_receipts))


def m_unsupported_measured_statuses(s: Session) -> Measurement:
    """Anything asserting observation without a receipt or an evidence object behind it.

    Three places can assert it: a claim's status, a verdict's outcome, and the composer's own
    `measured_anything` flag. All three are checked, because a synthesis that says an instrument
    ran is the one a reader believes even when the graph disagrees.
    """
    have_support = bool(s.capability_receipts) or bool(s.evidence)
    offenders: List[Dict[str, str]] = []
    for c in s.claims:
        if _s(c.get("status")) in MEASURED_STATUSES and not have_support:
            offenders.append({"kind": "claim", "id": _s(c.get("claim_id")),
                              "status": _s(c.get("status"))})
    for v in s.verdicts:
        outcome = _s(v.get("outcome"))
        if outcome in ("measured", "supported_by_measurement") \
                and not (_l(v.get("evidence_refs")) or _l(v.get("receipt_refs"))):
            offenders.append({"kind": "verdict", "id": _s(v.get("verdict_id")), "status": outcome})
    prov = _d(s.synthesis.get("provenance"))
    if prov.get("measured_anything") is True and not have_support:
        offenders.append({"kind": "synthesis", "id": _s(s.synthesis.get("synthesis_id")),
                          "status": "measured_anything=true with no receipt and no evidence"})
    if prov.get("simulated_capability") is True:
        offenders.append({"kind": "synthesis", "id": _s(s.synthesis.get("synthesis_id")),
                          "status": "simulated_capability=true"})
    return count(len(offenders), detail=offenders)


def m_synthesis_asserts_capability_without_receipt(s: Session) -> Measurement:
    """Does the answer's own prose say an instrument ran, when no receipt says one did?

    THE FLAGS AND THE PROSE ARE CHECKED SEPARATELY, because in the baseline they disagree. The
    composer set `measured_anything=false` and `simulated_capability=false` — both correct — and
    then opened its note with "one capability was invoked and it was a declared SIMULATION" over a
    capability stage whose own summary reads "nothing was commissioned". The structured fields were
    honest; the sentence a person actually reads was not.

    A PROSE MATCH IS A DETECTOR, NOT A VERDICT. Every hit carries the matched sentence so it can be
    read, and the measurement carries a warning saying so. What raises it from suggestive to
    contradictory is the receipt count: prose asserting an invocation with zero receipts and zero
    evidence is a disagreement inside one record, whatever the sentence turns out to mean.
    """
    if not s.synthesis:
        return refuse("count", "no synthesis was composed, so its prose asserts nothing.")
    texts: List[Tuple[str, str]] = [("note", _s(s.synthesis.get("note")))]
    for sec in _l(s.synthesis.get("sections")):
        texts.append((_s(_d(sec).get("section_id")), _s(_d(sec).get("text"))))

    hits: List[Dict[str, str]] = []
    for where, text in texts:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if any(p.search(sentence) for p in CAPABILITY_ASSERTIONS):
                hits.append({"where": where, "sentence": sentence.strip()})

    supported = len(s.capability_receipts) > 0 or len(s.evidence) > 0
    if not hits:
        return count(0)
    if supported:
        return count(0, detail={"asserted_and_supported": hits,
                                "receipts": len(s.capability_receipts),
                                "evidence": len(s.evidence)},
                     warning="the answer says a capability ran and receipts exist; the two were "
                             "not checked against each other beyond counting.")
    return count(len(hits), detail=hits,
                 warning="matched by sentence pattern. Read the sentences in `detail` before "
                         "citing this: the contradiction being reported is with the receipt count, "
                         "not with the wording.")


def m_answer_sections_total(s: Session) -> Measurement:
    if not s.synthesis:
        return refuse("count", "no synthesis was composed.")
    return count(len(_l(s.synthesis.get("sections"))))


def m_answer_sections_with_refs(s: Session) -> Measurement:
    if not s.synthesis:
        return refuse("count", "no synthesis was composed.")
    sections = [_d(x) for x in _l(s.synthesis.get("sections"))]
    if not sections:
        return refuse("count", "the synthesis carries no sections.")
    n = sum(1 for x in sections
            if _l(x.get("claim_refs")) or _l(x.get("relation_refs")) or _l(x.get("refs")))
    return count(n, detail={"of_total": len(sections)})


def m_contradiction_preserved(s: Session) -> Measurement:
    """Did anything in the record disagree with, complicate or refuse the premise?

    Three ways it can be evidenced, and any one is enough: a contrast relation, a recorded refusal,
    or a semantic remainder entry. A run may legitimately reach disagreement by any of them, and
    demanding a specific one would be scoring the shape of the record rather than its content.
    """
    contrasts = [_s(e.get("edge_id")) for e in s.edges if _s(e.get("kind")) in CONTRAST_KINDS]
    refusals = [_s(r.get("refusal_id")) for r in s.refusals]
    remainder = [_s(r.get("remainder_id") or r.get("id")) for r in s.remainder]
    detail = {"contrast_edges": contrasts, "refusals": refusals[:20],
              "remainder_entries": len(remainder)}
    if contrasts or refusals or remainder:
        return flag(True, detail=detail)
    return flag(False, detail=detail)


def m_source_post_fingerprint_changes(s: Session) -> Measurement:
    """Compared against the case manifest by `evaluate`; this reports what the session itself says.

    A session that carries no fingerprints REFUSES. Reporting zero changes for a record that never
    recorded a fingerprint would be the strongest possible statement made from no evidence.
    """
    prints = {_s(p.get("post_id")): _s(p.get("fingerprint")) for p in s.posts}
    if not prints or not any(prints.values()):
        return refuse("count", "the session carries no source-post fingerprints, so nothing can be "
                               "said about whether the posts moved.")
    return count(0, detail={"fingerprints": prints,
                            "note": "the session's own fingerprints; compared with the case "
                                    "manifest under `inputs.fingerprint_changes`."})


def m_workflow_outcome(s: Session) -> Measurement:
    return Measurement(value=s.state or None, kind="label",
                       refused=None if s.state else "the session declares no state.",
                       detail={"stop_reason": s.stop_reason})


METRICS: Dict[str, Callable[[Session], Measurement]] = {
    "prompt_hypotheses_preserved": m_prompt_hypotheses_preserved,
    "prompt_hypothesis_atoms": m_prompt_hypothesis_atoms,
    "image_observation_atoms": m_image_observation_atoms,
    "observations_total": m_observations_total,
    "observations_per_image": m_observations_per_image,
    "observations_per_image_min": m_observations_per_image_min,
    "observations_with_image_refs": m_observations_with_image_refs,
    "observations_without_image_refs": m_observations_without_image_refs,
    "image_diversity_images_cited": m_image_diversity_images_cited,
    "image_diversity_balance": m_image_diversity_balance,
    "lexical_prompt_copy_ratio": m_lexical_prompt_copy_ratio,
    "claims_total": m_claims_total,
    "claims_sourced_only_from_prompt": m_claims_sourced_only_from_prompt,
    "claims_with_image_traceability": m_claims_with_image_traceability,
    "contrast_count": m_contrast_count,
    "cross_image_contrast_count": m_cross_image_contrast_count,
    "relation_count": m_relation_count,
    "cross_image_relation_count": m_cross_image_relation_count,
    "relation_source_completeness": m_relation_source_completeness,
    "relations_accepted_without_critique": m_relations_accepted_without_critique,
    "critic_accepted": m_critic_accepted,
    "critic_revised": m_critic_revised,
    "critic_rejected": m_critic_rejected,
    "truncated_stages": m_truncated_stages,
    "thin_stages": m_thin_stages,
    "unexamined_atoms": m_unexamined_atoms,
    "unexamined_claims": m_unexamined_claims,
    "unexamined_relation_batches": m_unexamined_relation_batches,
    "observables_proposed": m_observables_proposed,
    "capability_gaps": m_capability_gaps,
    "capability_receipts": m_capability_receipts,
    "unsupported_measured_statuses": m_unsupported_measured_statuses,
    "synthesis_asserts_capability_without_receipt":
        m_synthesis_asserts_capability_without_receipt,
    "answer_sections_total": m_answer_sections_total,
    "answer_sections_with_refs": m_answer_sections_with_refs,
    "contradiction_preserved": m_contradiction_preserved,
    "source_post_fingerprint_changes": m_source_post_fingerprint_changes,
    "workflow_outcome": m_workflow_outcome,
}


# ── diagnosis ───────────────────────────────────────────────────────────────

def _v(metrics: Mapping[str, Measurement], name: str) -> Any:
    m = metrics.get(name)
    return None if m is None else m.value


def diagnose(s: Session, metrics: Mapping[str, Measurement],
             case: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Findings first, then one semantic outcome — never the other way round.

    The semantic outcome is chosen from what the findings say, so it cannot be more optimistic than
    the evidence collected for it. `indeterminate` is a real answer and is used whenever the record
    is too thin to support any of the others; it is not a synonym for `adequate`.
    """
    findings: List[Dict[str, Any]] = []

    def add(code: str, severity: str, statement: str, evidence: Any = None) -> None:
        findings.append({"code": code, "severity": severity, "statement": statement,
                         "evidence": evidence})

    claims = _v(metrics, "claims_total") or 0
    relations = _v(metrics, "relation_count")
    cross = _v(metrics, "cross_image_relation_count")
    images = _v(metrics, "image_diversity_images_cited")
    prompt_only = _v(metrics, "claims_sourced_only_from_prompt")
    traceable = _v(metrics, "claims_with_image_traceability")
    truncated = metrics.get("truncated_stages")
    thin = metrics.get("thin_stages")
    unsupported = _v(metrics, "unsupported_measured_statuses")
    preserved = _v(metrics, "prompt_hypotheses_preserved")

    # THE HEADLINE. A comparative record with claims and no relations.
    if claims > 0 and relations == 0:
        add("relations_absent", "underperformance",
            f"{claims} claim(s) were compiled and no relation between any two of them was "
            f"produced. Whatever the claims are worth individually, no comparison was made.",
            {"claims": claims})
    elif isinstance(relations, int) and relations > 0 and cross == 0:
        add("relations_within_one_image", "underperformance",
            f"{relations} relation(s) were produced and none of them spans two images. A relation "
            f"between two claims about the same picture is not a comparison across the set.",
            {"relations": relations})

    if isinstance(images, int) and images == 0 and s.declared_post_ids():
        add("no_image_was_cited", "error",
            "the run was given images and no observation names any of them, so nothing in this "
            "record can be tied back to a picture.")
    elif isinstance(images, int) and 0 < images < len(s.declared_post_ids()):
        missing = sorted(set(s.declared_post_ids())
                         - set((metrics["image_diversity_images_cited"].detail or {})
                               .get("post_ids", [])))
        add("image_unread", "underperformance",
            f"{len(missing)} of {len(s.declared_post_ids())} image(s) were given to the run and "
            f"named by no observation.", {"post_ids": missing})

    if isinstance(prompt_only, int) and claims and prompt_only > claims / 2:
        add("prompt_dominated", "underperformance",
            f"{prompt_only} of {claims} claim(s) trace only to the prompt. More than half of what "
            f"this run 'found' is what it was told.", {"prompt_only": prompt_only, "claims": claims})

    if isinstance(traceable, int) and claims and traceable == 0:
        add("no_claim_reaches_an_image", "error",
            "no claim can be traced to a picture through its source spans.")

    if truncated is not None and (truncated.value or 0) > 0:
        add("stage_truncated", "underperformance",
            f"{truncated.value} stage/pass ended truncated: "
            f"{', '.join((truncated.detail or {}).get('stages', []))}. What is in the graph is what "
            f"fitted in the budget, not what there was.", truncated.detail)

    if thin is not None and (thin.value or 0) > 0:
        add("stage_thin", "underperformance",
            f"{thin.value} stage/pass ended thin or failed its coverage audit: "
            f"{', '.join((thin.detail or {}).get('stages', []))}.", thin.detail)

    prose = _v(metrics, "synthesis_asserts_capability_without_receipt")
    if isinstance(prose, int) and prose > 0:
        add("answer_asserts_an_instrument_that_did_not_run", "error",
            f"the answer's own prose asserts that a capability was invoked, and the record carries "
            f"{len(s.capability_receipts)} receipt(s) and {len(s.evidence)} evidence object(s). "
            f"The structured flags may well be honest; the sentence a person reads is not.",
            metrics["synthesis_asserts_capability_without_receipt"].detail)

    proposed = _v(metrics, "observables_proposed")
    receipts = _v(metrics, "capability_receipts")
    if isinstance(proposed, int) and proposed > 0 and receipts == 0:
        add("nothing_was_commissioned", "underperformance",
            f"{proposed} observable(s) were proposed and none was run. The run named what would "
            f"settle its claims and then settled none of them — which is a legitimate outcome, and "
            f"is not what a terminal state of `complete` conveys on its own.",
            {"observables": proposed})

    if isinstance(unsupported, int) and unsupported > 0:
        add("measured_without_support", "error",
            f"{unsupported} record(s) assert observation or measurement with no capability receipt "
            f"and no evidence object behind them.",
            metrics["unsupported_measured_statuses"].detail)

    if preserved is False:
        add("attribution_lost", "error",
            "a prompt clause reached the ledger attributed to something other than the person. The "
            "person's own assertion can no longer be told from a finding.",
            (metrics["prompt_hypotheses_preserved"].detail or {}))

    # Honest reporting of what nothing here can see.
    if metrics["relations_accepted_without_critique"].refused:
        add("no_relation_critique_contract", "note",
            "nothing in a session records whether a relation was reviewed, so accept / revise / "
            "reject were refused rather than reported as zero.")

    # ── the two outcomes ────────────────────────────────────────────────────
    workflow = s.state or None
    severities = {f["severity"] for f in findings}
    codes = {f["code"] for f in findings}

    if not s.claims and not s.blocks:
        semantic = "barren"
    elif "no_claim_reaches_an_image" in codes or "no_image_was_cited" in codes:
        semantic = "traceability_underperformed"
    elif "prompt_dominated" in codes:
        semantic = "prompt_dominated"
    elif "relations_absent" in codes or "relations_within_one_image" in codes:
        semantic = "relationally_underperformed"
    elif "error" in severities or "underperformance" in severities:
        semantic = "indeterminate"
    else:
        semantic = "adequate"

    terminal_ok = workflow in ("complete", "answered")
    disagree = bool(terminal_ok and semantic not in ("adequate",))
    if disagree:
        add("workflow_and_semantics_disagree", "underperformance",
            f"the machinery reported `{workflow}` while the record shows `{semantic}`. "
            f"The stop reason given was: {s.stop_reason or '(none)'}",
            {"workflow_outcome": workflow, "semantic_outcome": semantic})

    return {"workflow_outcome": workflow, "semantic_outcome": semantic,
            "outcomes_disagree": disagree, "findings": findings}


# ── expectations ────────────────────────────────────────────────────────────

def check_expectations(metrics: Mapping[str, Measurement],
                       case: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for prop in _l(case.get("expected_structural_properties")):
        name = _s(_d(prop).get("metric"))
        exp = _d(_d(prop).get("expectation"))
        row: Dict[str, Any] = {"metric": name, "expectation": exp,
                               "why": _s(_d(prop).get("why"))}
        if name not in METRICS:
            row["status"] = "unknown_metric"
            out.append(row)
            continue
        m = metrics.get(name)
        if m is None or m.value is None:
            row["status"] = "unmeasurable"
            row["observed"] = None
            row["why"] = (m.refused if m is not None and m.refused else row["why"])
            out.append(row)
            continue
        row["observed"] = m.value
        ok = True
        if "equals" in exp:
            ok = ok and m.value == exp["equals"]
        if exp.get("min") is not None:
            ok = ok and isinstance(m.value, (int, float)) and m.value >= exp["min"]
        if exp.get("max") is not None:
            ok = ok and isinstance(m.value, (int, float)) and m.value <= exp["max"]
        if exp.get("at_least_one"):
            ok = ok and bool(m.value)
        if exp.get("must_be_null"):
            ok = m.value is None
        row["status"] = "met" if ok else "unmet"
        out.append(row)
    return out


# ── the evaluation ──────────────────────────────────────────────────────────

def evaluate(session_raw: Mapping[str, Any], case: Optional[Mapping[str, Any]] = None,
             baseline: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    s = Session(session_raw)
    metrics = {name: fn(s) for name, fn in METRICS.items()}
    diagnosis = diagnose(s, metrics, case)

    case = _d(case)
    prompt_matches: Optional[bool] = None
    if case.get("prompt"):
        prompt_matches = (s.prompt == case["prompt"])

    # Fingerprints: the case says what the posts were; the session says what it read.
    changes: List[Dict[str, Any]] = []
    expected = {_s(f.get("post_id")): _s(f.get("fingerprint"))
                for f in _l(case.get("input_fingerprints"))}
    found = {_s(p.get("post_id")): _s(p.get("fingerprint")) for p in s.posts}
    for pid, want in expected.items():
        got = found.get(pid)
        if got is not None and want and got != want:
            changes.append({"post_id": pid, "expected": want, "found": got})
    if changes:
        diagnosis["findings"].append({
            "code": "source_post_moved", "severity": "error",
            "statement": f"{len(changes)} source post(s) do not match the fingerprint the case "
                         f"manifest recorded. Every result below is about different pixels.",
            "evidence": changes})

    prov = s.provenance
    depl = s.deployment
    unautomated = [f"{_d(f).get('shortcut')} — {_d(f).get('why')}"
                   for f in _l(case.get("forbidden_shortcuts"))
                   if _s(_d(f).get("detected_by")) == "none"]

    out: Dict[str, Any] = {
        "evaluation_version": EVALUATION_VERSION,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "case_ref": {"case_id": case.get("case_id"), "case_version": case.get("case_version"),
                     "prompt_sha256_matches": prompt_matches},
        "session_ref": {"session_id": s.session_id or None, "inquiry_id": s.inquiry_id or None,
                        "revision": s.revision, "schema_version": s.schema_version or None,
                        "state": s.state or None},
        "run_identity": {
            "deployment_kind": _s(depl.get("kind")) or None,
            "declared": depl.get("declared") if isinstance(depl.get("declared"), bool) else None,
            "reachable": depl.get("reachable") if isinstance(depl.get("reachable"), bool) else None,
            "provider": _d(s.synthesis.get("provenance")).get("provider"),
            "models": {"theorist": prov.get("theorist_model"), "compiler": prov.get("compiler_model"),
                       "composer": prov.get("composer_model"), "framer": prov.get("frame_producer")},
            "stage_bindings": _d(depl.get("stages")),
        },
        "inputs": {"post_ids": s.declared_post_ids(), "fingerprints": found,
                   "fingerprint_changes": changes},
        "metrics": {k: m.as_dict() for k, m in metrics.items()},
        "diagnosis": diagnosis,
        "manual_review": {
            "questions": [_s(q) for q in _l(case.get("manual_review_questions"))],
            "note": "These are not scored and are not proxied. Aesthetic quality and philosophical "
                    "depth are outside what this harness can decide.",
            "unautomated_shortcuts": unautomated,
        },
        "timing": {"stage_ms": {_s(x.get("stage")): x.get("duration_ms") for x in s.stages}},
    }
    if case:
        out["diagnosis"]["expectations"] = check_expectations(metrics, case)
    out["baseline_comparison"] = compare_to_baseline(out, baseline) if baseline else None
    return out


def compare_to_baseline(evaluation: Mapping[str, Any],
                        baseline: Mapping[str, Any]) -> Dict[str, Any]:
    """Metric-by-metric delta. A metric that refused on either side is reported as such, not as 0."""
    rows: Dict[str, Any] = {}
    now = _d(evaluation.get("metrics"))
    was = _d(baseline.get("metrics"))
    for name in sorted(set(now) | set(was)):
        a, b = _d(was.get(name)).get("value"), _d(now.get(name)).get("value")
        row: Dict[str, Any] = {"baseline": a, "current": b}
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                and not isinstance(a, bool) and not isinstance(b, bool):
            row["delta"] = b - a
        elif a is None or b is None:
            row["delta"] = None
            row["note"] = "one side refused; a delta would invent a comparison."
        rows[name] = row
    return {"baseline_case": _d(baseline.get("case_ref")).get("case_id"),
            "baseline_session": _d(baseline.get("session_ref")).get("session_id"),
            "metrics": rows}


# ── sanitizing an external export into a committed fixture ──────────────────

SECRET_KEYS = re.compile(
    r"(api[_-]?key|secret|token|authorization|password|cookie|bearer)", re.I)


def sanitize(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Strip credentials and outbound URLs; keep every structural fact.

    URLs go because a committed fixture that carries live image links is a fixture that fetches
    the internet on somebody's laptop. They are replaced by a stable digest so the SHAPE of the
    field is preserved — `image_ref == image_url` is a real production property, and a fixture
    that dropped both would stop being able to demonstrate it.
    """
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if SECRET_KEYS.search(str(k)):
                    out[k] = "[redacted]"
                elif isinstance(v, str) and v.startswith(("http://", "https://")):
                    out[k] = "urn:sanitized:" + hashlib.sha256(v.encode()).hexdigest()[:32]
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, str) and node.startswith(("http://", "https://")):
            return "urn:sanitized:" + hashlib.sha256(node.encode()).hexdigest()[:32]
        return node
    return walk(dict(raw))


# ── CLI ─────────────────────────────────────────────────────────────────────

def load_case(case_id: str) -> Dict[str, Any]:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise SystemExit(f"no such case: {case_id} (looked in {CASES_DIR})")
    return json.loads(path.read_text())


def _text_report(ev: Mapping[str, Any]) -> str:
    lines: List[str] = []
    dg = _d(ev.get("diagnosis"))
    cr = _d(ev.get("case_ref"))
    lines.append(f"case      {cr.get('case_id') or '(none)'} v{cr.get('case_version') or '-'}"
                 + ("" if cr.get("prompt_sha256_matches") is not False
                    else "   ** PROMPT DOES NOT MATCH THIS CASE **"))
    sr = _d(ev.get("session_ref"))
    lines.append(f"session   {sr.get('session_id')} rev {sr.get('revision')}  "
                 f"[{_d(ev.get('run_identity')).get('deployment_kind')}]")
    lines.append(f"workflow  {dg.get('workflow_outcome')}")
    lines.append(f"semantic  {dg.get('semantic_outcome')}"
                 + ("   <- DISAGREE" if dg.get("outcomes_disagree") else ""))
    lines.append("")
    lines.append("metrics")
    for name, m in _d(ev.get("metrics")).items():
        val = m.get("value")
        if val is None:
            shown = "refused"
        elif isinstance(val, float):
            shown = f"{val:.3f}"
        elif isinstance(val, dict):
            shown = json.dumps(val)
        else:
            shown = str(val)
        mark = " !" if m.get("warning") else ""
        lines.append(f"  {name:<38} {shown}{mark}")
        if val is None:
            lines.append(f"      ↳ {m.get('refused')}")
        elif m.get("warning"):
            lines.append(f"      ↳ {m.get('warning')}")
    lines.append("")
    lines.append("findings")
    for f in _l(dg.get("findings")):
        lines.append(f"  [{_d(f).get('severity').upper()}] {_d(f).get('code')}")
        lines.append(f"      {_d(f).get('statement')}")
    if _l(dg.get("expectations")):
        lines.append("")
        lines.append("expectations")
        for e in _l(dg.get("expectations")):
            e = _d(e)
            lines.append(f"  {e.get('status'):<14} {e.get('metric')}  "
                         f"expected {json.dumps(e.get('expectation'))}, observed "
                         f"{json.dumps(e.get('observed'))}")
    mr = _d(ev.get("manual_review"))
    lines.append("")
    lines.append("NOT DECIDED HERE — for a person to answer")
    for q in _l(mr.get("questions")):
        lines.append(f"  ? {q}")
    for u in _l(mr.get("unautomated_shortcuts")):
        lines.append(f"  ! caught by nothing automatic: {u}")
    return "\n".join(lines)


def archive(ev: Mapping[str, Any], session_raw: Mapping[str, Any],
            case: Optional[Mapping[str, Any]], out_dir: Path,
            *, from_fixture: Optional[str] = None) -> Path:
    """Write one run directory.

    `from_fixture` names a committed fixture the session came from, and when given the archive
    stores a POINTER with the fixture's digest instead of a second copy of it. Two reasons, and
    the second is the real one: 300KB of identical JSON twice is waste, but a copy that can drift
    from the file it was copied from is a record that will eventually disagree with itself. A live
    run has no fixture behind it and gets the full sanitized session, because there the archive is
    the only place that record exists.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation.json").write_text(json.dumps(ev, indent=2) + "\n")
    if from_fixture:
        src = FIXTURES_DIR / f"{from_fixture}.sanitized.json"
        (out_dir / "session.source.json").write_text(json.dumps({
            "fixture": from_fixture,
            "path": str(src.relative_to(ROOT)),
            "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
            "note": "the session is the committed fixture named above, not a copy of it. The "
                    "digest is here so a fixture edited after this run was archived is a "
                    "detectable mismatch rather than a silent one.",
        }, indent=2) + "\n")
    else:
        (out_dir / "session.raw.json").write_text(
            json.dumps(sanitize(session_raw), indent=2) + "\n")
    if case:
        (out_dir / "manifest.json").write_text(json.dumps(case, indent=2) + "\n")
    (out_dir / "report.txt").write_text(_text_report(ev) + "\n")
    (out_dir / "timing.json").write_text(json.dumps(_d(ev.get("timing")), indent=2) + "\n")
    (out_dir / "run_identity.json").write_text(
        json.dumps(_d(ev.get("run_identity")), indent=2) + "\n")
    return out_dir


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", type=Path, help="a session export to evaluate")
    ap.add_argument("--fixture", help="a committed fixture name under fixtures/")
    ap.add_argument("--case", help="case id to evaluate against")
    ap.add_argument("--baseline", type=Path, help="a prior evaluation.json to compare against")
    ap.add_argument("--import-baseline", type=Path,
                    help="sanitize an external export into a committed fixture")
    ap.add_argument("--fixture-name", default="baseline-rev6")
    ap.add_argument("--archive", action="store_true", help="write a run directory under runs/")
    ap.add_argument("--json", action="store_true", help="print the evaluation as JSON")
    ap.add_argument("--report-contradictions", action="store_true",
                    help="print the contract facts this evaluator had to discover from a payload")
    args = ap.parse_args(argv)

    if args.report_contradictions:
        for title, body in CONTRACT_CONTRADICTIONS:
            print(f"* {title}\n    {body}\n")
        return 0

    if args.import_baseline:
        raw = json.loads(args.import_baseline.read_text())
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        dest = FIXTURES_DIR / f"{args.fixture_name}.sanitized.json"
        dest.write_text(json.dumps(sanitize(raw), indent=2) + "\n")
        print(f"wrote {dest} ({dest.stat().st_size} bytes)")
        return 0

    if args.fixture:
        path = FIXTURES_DIR / f"{args.fixture}.sanitized.json"
    elif args.session:
        path = args.session
    else:
        ap.error("one of --session, --fixture or --import-baseline is required")
    raw = json.loads(Path(path).read_text())

    case = load_case(args.case) if args.case else None
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    ev = evaluate(raw, case, baseline)

    if args.json:
        print(json.dumps(ev, indent=2))
    else:
        print(_text_report(ev))

    if args.archive:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"{stamp}-{(case or {}).get('case_id', 'uncased')}"
        print(f"\narchived -> "
              f"{archive(ev, raw, case, RUNS_DIR / name, from_fixture=args.fixture or None)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
