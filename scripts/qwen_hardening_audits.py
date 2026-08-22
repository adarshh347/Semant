#!/usr/bin/env python3
"""
INTELLIGENCE-001C-R1 — the two audits, with no network in them.

PURE ON PURPOSE. Everything here is a function of text and of a frozen observation inventory, so
the whole of Parts 4 and 5 can be tested without a model loaded, without a server running and
without the six gigabytes of weights that produced the evidence. An honesty guard that could only
be exercised by calling the thing it guards would never be exercised in CI.

TWO INSTRUMENTS.

    `audit_precision`  — what kind of number is this? A count of visible things, the schema's own
                         uncertainty category, a quantity nothing measured, or something a reader
                         has to look at. #230 could only say "measurement grammar" and therefore
                         could not tell its own false positive from a real fabrication.

    `critique_alignment` — did this alignment earn its conclusion? Citations that exist, citations
                         that belong to an image in the inventory, a stance that moves the claim
                         resting on something, and the three specific ways #230's captured run was
                         fluent and wrong.

NEITHER ASKS A MODEL ANYTHING. Telling a model to be sceptical is a wish; these are checks run
over what it returned. And neither contains a material, genre, period or subject word — point them
at a corpus of trains and they work unchanged, which is what rule 5 requires.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT), str(REPO_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import local_qwen_vlm_lab as lab                                            # noqa: E402


# ── Part 4 — unsupported interpretive precision ──────────────────────────────
#
# #230 caught its own failure with a percentage pattern and then could say nothing more than "one
# trial wrote measurement grammar". The offending sentence was:
#
#     "The suggested uncertainty is 10% for 'polished' versus a very dense, smooth ceramic."
#
# A number invented for the model's OWN CONFIDENCE, in a record whose `uncertainty` field is a
# three-value enum and whose `status` field cannot say `measured`. The grammar held; the prose
# beside it did not.
#
# The repair is not to delete the sentence. It is to say precisely WHAT KIND of number it is,
# because these four are different things and a single "measurement grammar" flag conflates them:
#
#     a count of things visible in the picture        three windows      LEGITIMATE
#     the declared uncertainty category               medium             LEGITIMATE
#     a quantity nothing measured                     10% · 30 degrees   INVALID
#     a bare number in unclear service                a 2:1 feel         REVIEW
#
# Condemning the first would make the audit useless: an observer that may not say how many windows
# it can see is not an observer. So the classifier is context-sensitive and topic-independent —
# no material, no genre, no period word appears anywhere in it.

#: `in` IS NOT IN THIS LIST. It is the commonest preposition in English and `0.85 in this reading`
#: read as inches; a unit alias that collides with a function word makes the audit unreadable
#: exactly where it is about to be believed. `inch`/`inches` stay.
_UNITS = (r"mm|cm|km|metres?|meters?|inch|inches|ft|feet|kg|lbs?|"
          r"°|deg|degrees?|px|pixels?|microns?")

#: The vocabulary of self-assessed confidence. A number NEAR one of these is a model scoring
#: itself, which no capability has measured and no schema asked for.
_CERTAINTY_CONTEXT = re.compile(
    r"\b(?:confidence|confident|certaint(?:y|ies)|uncertaint(?:y|ies)|uncertain|probabilit(?:y|ies)|"
    r"likelihood|likely|odds|sure|sureness|accuracy|precision|reliabilit(?:y|ies))\b", re.I)

#: The enum this lab's observation schema actually offers. These words are the SANCTIONED way to
#: express uncertainty and must never be flagged, or the audit would punish compliance.
_DECLARED_CATEGORIES = re.compile(r"^(?:low|medium|high)$", re.I)

_NUMBER_WORD = (r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                r"dozen|several|few")

CANDIDATE_PATTERNS: List[Tuple[str, str]] = [
    ("percentage", r"\b\d+(?:\.\d+)?\s*(?:%|per\s?cent\b|percent\b)"),
    ("dimension", rf"\b\d+(?:\.\d+)?\s*(?:{_UNITS})\b"),
    ("ratio", r"\b\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?\b"),
    ("decimal", r"(?<![\w.])\d?\.\d+(?![\w.])"),
    ("measurement_verb", r"\bmeasur(?:ed|ement|ements|es)\b|\bcalibrat(?:ed|ion)\b|"
                         r"\bquantif(?:y|ied)\b"),
    ("precision_adverb", r"\b(?:exactly|precisely)\b"),
    ("integer", r"(?<![\w.])\d{1,3}(?![\w.%])"),
    ("number_word", rf"\b(?:{_NUMBER_WORD})\b"),
    ("category_word", r"\b(?:low|medium|high)\b"),
]

#: A number followed by something countable is a count. Checked as SHAPE — a plural noun, or a
#: partitive `of the` — so it carries no topic vocabulary.
_COUNTABLE_AFTER = re.compile(r"^\s*(?:[a-z]+(?:ly)?\s+){0,2}[a-z]{3,}s\b|^\s*of\s+(?:the|these|its)\b",
                              re.I)
_GEOMETRIC_AFTER = re.compile(
    r"^\s*(?:\d|one|two|half|at the|on the|along the|aligned|parallel|perpendicular|"
    r"vertical|horizontal|centred|centered|symmetrical)", re.I)

CLASSES = ("allowed_source_visible_quantity", "declared_uncertainty_category",
           "unsupported_measurement", "ambiguous_requires_review")


def classify_precision(kind: str, match: str, before: str, after: str) -> Tuple[str, str]:
    """
    One candidate, classified by what surrounds it. Returns (class, why).

    ORDER MATTERS AND IS THE ARGUMENT. Certainty context is checked FIRST, because `10%` is a
    percentage in isolation and a fabricated self-score in `the suggested uncertainty is 10%` —
    and it is the second reading that #230 needed and could not produce.
    """
    near = f"{before} {match} {after}"
    certainty_near = bool(_CERTAINTY_CONTEXT.search(near))

    if kind in ("percentage", "decimal", "ratio") and certainty_near:
        return ("unsupported_measurement",
                "a number attached to the model's own confidence. No capability measured it, and "
                "the schema already offers a declared category for exactly this")
    if kind == "dimension":
        return ("unsupported_measurement", "a quantity with a unit, from a photograph")
    if kind == "percentage":
        return ("unsupported_measurement", "a proportion nothing measured")
    if kind == "ratio":
        return ("unsupported_measurement", "a stated ratio nothing measured")
    if kind == "measurement_verb":
        return ("unsupported_measurement", "the language of measurement, with no measurement")
    if kind == "precision_adverb":
        if _GEOMETRIC_AFTER.match(after):
            return ("unsupported_measurement",
                    "a precision claim about a quantity or an alignment")
        return ("allowed_source_visible_quantity",
                "an adverb of manner about craft, not a measurement — `precisely executed` is a "
                "claim about carving and flagging it is the audit crying wolf")
    if kind == "category_word":
        if _DECLARED_CATEGORIES.match(match.strip()):
            return ("declared_uncertainty_category",
                    "the sanctioned vocabulary of the observation schema's own enum")
        return ("ambiguous_requires_review", "a category word in unclear service")
    if kind == "decimal":
        return ("ambiguous_requires_review",
                "a bare decimal with nothing nearby to say what it counts")
    if kind in ("integer", "number_word"):
        if certainty_near:
            return ("unsupported_measurement",
                    "a count standing in for the model's own confidence")
        if _COUNTABLE_AFTER.match(after):
            return ("allowed_source_visible_quantity",
                    "a count of things in the picture. An observer that may not say how many "
                    "windows it can see is not an observer")
        return ("ambiguous_requires_review",
                "a number with no countable noun and no unit after it")
    return ("ambiguous_requires_review", "unrecognised candidate shape")


def audit_precision(text: str, window: int = 70) -> Dict[str, Any]:
    """
    Every numeric and precision expression in a piece of interpretive prose, classified.

    Topic-independent by construction: there is no material, genre, period or subject word in the
    tables above, so this works unchanged on a corpus of trains.
    """
    text = text or ""
    findings: List[Dict[str, Any]] = []
    # LONGEST MATCH WINS, and a candidate inside another is dropped. `30 degrees` and the `30`
    # inside it are one expression; recording both made a single fabricated dimension report as
    # one unsupported finding AND one allowed count, which is a count nobody can read.
    spans: List[Tuple[int, int]] = []
    for kind, pat in CANDIDATE_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            span = (m.start(), m.end())
            if any(a <= span[0] and span[1] <= b for a, b in spans):
                continue
            spans.append(span)
            before = text[max(0, m.start() - window):m.start()]
            after = text[m.end():m.end() + window]
            cls, why = classify_precision(kind, m.group(0), before, after)
            findings.append({
                "kind": kind, "match": m.group(0), "span": list(span),
                "classification": cls, "why": why,
                "context": (before[-40:] + "«" + m.group(0) + "»" + after[:40]).strip(),
            })
    unsupported = [f for f in findings if f["classification"] == "unsupported_measurement"]
    ambiguous = [f for f in findings if f["classification"] == "ambiguous_requires_review"]
    return {
        "findings": findings,
        "counts": {c: sum(1 for f in findings if f["classification"] == c) for c in CLASSES},
        "unsupported": unsupported,
        "ambiguous": ambiguous,
        "epistemically_valid": not unsupported,
        "verdict": "invalid" if unsupported else ("review" if ambiguous else "valid"),
        "note": "A source-visible count and a declared uncertainty category are NOT condemned. "
                "Only a quantity nothing measured invalidates a response; an ambiguous one asks "
                "for a reader.",
    }


def audit_observation_record(parsed: Any) -> Dict[str, Any]:
    """
    The audit, applied field by field to a structured observation so a finding points at a field
    rather than at a blob. The `uncertainty` enum field is skipped — auditing the sanctioned
    vocabulary would flag every compliant record ever written.
    """
    per_field: List[Dict[str, Any]] = []
    obs = (parsed or {}).get("observations") or []
    for i, o in enumerate(obs):
        for f in ("locus", "visible_organization", "surface_light_behavior",
                  "apparent_material_effect"):
            a = audit_precision(o.get(f) or "")
            if a["findings"]:
                per_field.append({"observation_index": i, "field": f, **a})
    for j, c in enumerate((parsed or {}).get("cannot_determine") or []):
        a = audit_precision(c or "")
        if a["findings"]:
            per_field.append({"cannot_determine_index": j, "field": "cannot_determine", **a})
    unsupported = [x for x in per_field if not x["epistemically_valid"]]
    return {
        "per_field": per_field,
        "unsupported_fields": [{"observation_index": x.get("observation_index"),
                                "field": x["field"],
                                "matches": [f["match"] for f in x["unsupported"]]}
                               for x in unsupported],
        "epistemically_valid": not unsupported,
        "skipped_fields": ["uncertainty"],
        "why_skipped": "it is the schema's own enum. Auditing the sanctioned vocabulary would "
                       "flag every compliant record ever written.",
    }


# ── Part 5 — the claim critic ────────────────────────────────────────────────
#
# #230's captured run did not fail by being incoherent. It failed by being FLUENT AND WRONG in
# three specific, checkable ways, and every one of them is a rule below:
#
#   it quoted a property every compared object has, to support a claim that they undergo the
#   SAME process. A predicate true of all of them cannot separate the claim from its negation.
#                                                      -> non_discriminative_evidence
#
#   it cited "woven/braided styles" — a description of DIVERSITY — as evidence of sameness, with
#   nothing joining the two.                           -> diversity_used_for_sameness
#
#   it manufactured a claim the person never made and asserted the observations "explicitly deny"
#   it.                                                -> minted_claim, and now impossible: the
#                                                         claim ids are an enum in the grammar
#
# NONE OF THIS ASKS THE MODEL TO BE CRITICAL. Telling a model to be sceptical is a wish. These are
# checks run over what it returned, and a failure marks the alignment invalid while preserving it
# whole.

_CONTRAST_MARKERS = re.compile(
    r"\b(?:whereas|while|unlike|differs?|different(?:ly)?|varies|varying|variation|"
    r"in contrast|by contrast|on the other hand|however|but|although|though|distinct|"
    r"diverge|divergent)\b", re.I)

_BRIDGE_MARKERS = re.compile(
    r"\b(?:because|therefore|which means|so that|hence|thus|it follows|consequently|"
    r"even though .* still|despite .* the)\b", re.I)

_ABSENCE_AS_SUPPORT = re.compile(
    r"\b(?:no|none of the|nothing in the|not one)\s+(?:\w+\s+){0,3}"
    r"(?:contradict\w*|deny|denies|denied|refut\w*|rule[sd]? out|disprove\w*|"
    r"argues? against|speaks? against)\b", re.I)

#: Straight, curly and back-quoted spans. A model arguing from evidence quotes it, and the quote
#: is the part whose genericness can be tested without guessing which clause was the argument.
_QUOTED = re.compile(r"[\"\u201c\u2018']([^\"\u201d\u2019']{8,240})[\"\u201d\u2019']")

_UNIVERSAL_GRAMMAR = re.compile(
    r"\b(?:all|every|each|any|same|identical|one thing|uniform(?:ly)?|always|invariabl\w+)\b", re.I)

CRITIC_CHECKS = (
    "unknown_citation",
    "malformed_citation",
    "wrong_image_citation",
    "missing_citation_for_moving_disposition",
    "single_image_support_for_universal_claim",
    "non_discriminative_evidence",
    "generic_quoted_evidence",
    "diversity_used_for_sameness",
    "absence_of_contradiction_as_support",
    "minted_claim",
    "missing_claim",
    "duplicate_claim",
)

MOVING_DISPOSITIONS = ("supports", "challenges")


def observation_index(exp1: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, set], List[str]]:
    """
    The frozen inventory, as three things the critic needs: id -> text, image -> content words,
    and the list of image refs.
    """
    by_id: Dict[str, str] = {}
    by_image: Dict[str, set] = {}
    refs: List[str] = []
    for img in exp1.get("images") or []:
        ref = img["ref"]
        refs.append(ref)
        words: set = set()
        for j, o in enumerate((img.get("parsed") or {}).get("observations") or []):
            text = " ".join(str(o.get(f) or "") for f in
                            ("locus", "visible_organization", "surface_light_behavior",
                             "apparent_material_effect"))
            by_id[f"{ref}-o{j}"] = text
            words |= lab._content_words(text)
        for c in (img.get("parsed") or {}).get("cannot_determine") or []:
            by_id[f"{ref}-undetermined"] = str(c)
        by_image[ref] = words
    return by_id, by_image, refs


def universal_terms(by_image: Dict[str, set]) -> set:
    """
    Content words that appear in EVERY image's observations.

    This is the operational meaning of "generic". A term the observer used about all three objects
    cannot, by itself, tell them apart — so an explanation built only from these words is not
    discriminating anything, whatever it asserts.
    """
    sets = [w for w in by_image.values() if w]
    if not sets:
        return set()
    out = set(sets[0])
    for w in sets[1:]:
        out &= w
    return out


#: How much of a quote's vocabulary an image's observations have to contain before the quote counts
#: as describing that image too. 0.6 is this lane's number and it is a REVIEW threshold, never a
#: verdict — see `reviews` below for why the strict form could not be made decisive.
GENERIC_COVERAGE = 0.6

CRITIC_REVIEWS = ("possibly_generic_quoted_evidence",)


def quote_coverage(quote: str, by_image: Dict[str, set]) -> Dict[str, float]:
    qw = lab._content_words(quote)
    if not qw:
        return {}
    return {ref: round(len(qw & words) / len(qw), 3) for ref, words in by_image.items()}


def critique_alignment(parsed: Any, claims: List[Dict[str, str]],
                       exp1: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic checks over one alignment. Returns the findings and a validity verdict; the
    caller PRESERVES the candidate whole and marks it invalid rather than discarding it.

    TWO TIERS, AND THE SECOND EXISTS BECAUSE THE FIRST COULD NOT BE STRETCHED HONESTLY.
    `findings` invalidate. `reviews` do not — they are put in front of a person.

    The directive asks for a check that "generic facts such as `all are carved from a solid mass`
    cannot establish a discriminative stylistic relation". The fully general form of that is not
    deterministically decidable: it asks whether a predicate would still hold if the claim were
    false, which needs world knowledge, and the only way to encode the world knowledge is a list
    of generic predicates — which is precisely the topic vocabulary rule 5 forbids.

    So the strict check fires only when a quote is built ENTIRELY from vocabulary the observer used
    about every image. That is sound and never wrong when it fires; it is also conservative, and
    on #230's own captured run it does not fire, because that run quoted a phrase whose key
    terms one image's observations never used. The coverage-based
    version catches that case and is reported as a REVIEW, because a threshold is a judgement and
    calling a judgement a verdict is the mistake this whole lab exists to avoid.
    """
    by_id, by_image, refs = observation_index(exp1)
    universal = universal_terms(by_image)
    wanted_ids = [c["id"] for c in claims]
    kinds = {c["id"]: c.get("kind", "") for c in claims}
    texts = {c["id"]: c.get("text", "") for c in claims}

    dispositions = (parsed or {}).get("dispositions") or []
    findings: List[Dict[str, Any]] = []
    reviews: List[Dict[str, Any]] = []

    def flag(check: str, claim_id: Optional[str], detail: str, evidence: Any = None) -> None:
        assert check in CRITIC_CHECKS, check
        findings.append({"check": check, "user_claim_id": claim_id,
                         "detail": detail, "evidence": evidence})

    def review(check: str, claim_id: Optional[str], detail: str, evidence: Any = None) -> None:
        assert check in CRITIC_REVIEWS, check
        reviews.append({"check": check, "user_claim_id": claim_id,
                        "detail": detail, "evidence": evidence})

    seen_ids: List[str] = []
    for d in dispositions:
        cid = d.get("user_claim_id")
        seen_ids.append(cid)
        if cid not in wanted_ids:
            flag("minted_claim", cid,
                 "a claim id that was not supplied. The grammar should make this impossible; "
                 "if it appears, the enum was not injected", cid)
            continue

        disp = d.get("disposition")
        cites = [lab.normalize_oid(o) for o in (d.get("observation_ids") or [])]
        expl = d.get("discriminative_explanation") or ""

        unknown = [c for c in cites if c not in by_id]
        for c in unknown:
            if re.match(r"^[a-z0-9-]+-o\d+$", c) or c.endswith("-undetermined"):
                flag("unknown_citation", cid,
                     "well-formed, and points at an observation that was never written", c)
            else:
                flag("malformed_citation", cid,
                     "not an observation id at all. A grammar constrains shape, never a foreign "
                     "key", c)

        known = [c for c in cites if c in by_id]
        bad_image = [c for c in known if c.rsplit("-o", 1)[0].replace("-undetermined", "")
                     not in refs]
        for c in bad_image:
            flag("wrong_image_citation", cid, "cites an image not in this inventory", c)

        if disp in MOVING_DISPOSITIONS and not known:
            flag("missing_citation_for_moving_disposition", cid,
                 f"`{disp}` moves the claim and rests on nothing. `does_not_bear_on` and "
                 f"`cannot_determine` may legitimately cite nothing; these two may not", cites)

        is_universal = (kinds.get(cid) == "universal_sameness"
                        or bool(_UNIVERSAL_GRAMMAR.search(texts.get(cid, ""))))

        if is_universal and disp == "supports" and known:
            images_cited = {c.split("-o")[0].replace("-undetermined", "") for c in known}
            if len(images_cited) < len(refs):
                flag("single_image_support_for_universal_claim", cid,
                     f"a claim about all {len(refs)} objects, supported from "
                     f"{len(images_cited)} of them", sorted(images_cited))

        if disp in MOVING_DISPOSITIONS and known:
            expl_words = lab._content_words(expl)
            distinctive = expl_words - universal
            if not distinctive:
                flag("non_discriminative_evidence", cid,
                     "the explanation is built entirely from terms the observer used about EVERY "
                     "image. A property shared by all the compared objects cannot, by itself, "
                     "establish a relation between them",
                     {"universal_terms_used": sorted(expl_words & universal)[:12]})

            # THE INSTRUMENT THAT ACTUALLY BITES. Checking the whole explanation for zero
            # distinctive words never fires — a paragraph always contains something. But a model
            # arguing from evidence QUOTES it, and #230's captured run quoted a
            # property every object had, to prove the three shared one process.
            # Every content word of that quote is one the observer used about all three, so the
            # quote cannot separate the claim from its negation however true it is.
            for q in _QUOTED.findall(expl):
                qw = lab._content_words(q)
                if len(qw) >= 2 and not (qw - universal):
                    flag("generic_quoted_evidence", cid,
                         "the quoted evidence is true of every object compared, so it cannot "
                         "establish a relation between them. A generic fact is not a "
                         "discriminative one",
                         {"quote": q[:120], "all_terms_universal": sorted(qw)[:10]})
                elif is_universal and len(qw) >= 3:
                    cov = quote_coverage(q, by_image)
                    if cov and min(cov.values()) >= GENERIC_COVERAGE:
                        review("possibly_generic_quoted_evidence", cid,
                               f"every image's observations contain at least "
                               f"{int(GENERIC_COVERAGE * 100)}% of this quote's vocabulary, so it "
                               f"may describe all of them equally and prove nothing about their "
                               f"relation. A threshold is a judgement, so this is put to a reader "
                               f"rather than used to invalidate",
                               {"quote": q[:120], "coverage": cov})

        if is_universal and disp == "supports":
            if _CONTRAST_MARKERS.search(expl) and not _BRIDGE_MARKERS.search(expl):
                flag("diversity_used_for_sameness", cid,
                     "the explanation describes difference and concludes sameness, with no "
                     "bridging argument joining the two",
                     {"contrast": _CONTRAST_MARKERS.findall(expl)[:5]})

        if disp == "supports" and _ABSENCE_AS_SUPPORT.search(expl):
            flag("absence_of_contradiction_as_support", cid,
                 "nothing contradicting a claim is not evidence for it",
                 _ABSENCE_AS_SUPPORT.search(expl).group(0))

    for cid in wanted_ids:
        if cid not in seen_ids:
            flag("missing_claim", cid, "supplied and never disposed of", None)
    for cid in set(seen_ids):
        if cid and seen_ids.count(cid) > 1:
            flag("duplicate_claim", cid, f"disposed of {seen_ids.count(cid)} times", None)

    stances = {}
    for d in dispositions:
        stances[d.get("disposition")] = stances.get(d.get("disposition"), 0) + 1

    resisted = sum(v for k, v in stances.items() if k in ("challenges", "complicates"))
    accepted = stances.get("supports", 0)
    n = len(dispositions)
    return {
        "findings": findings,
        "reviews": reviews,
        "counts": {c: sum(1 for f in findings if f["check"] == c) for c in CRITIC_CHECKS},
        "review_counts": {c: sum(1 for f in reviews if f["check"] == c) for c in CRITIC_REVIEWS},
        "valid": not findings,
        "needs_review": bool(reviews),
        "stances": stances,
        "n_dispositions": n,
        "all_resisted": bool(n) and accepted == 0 and resisted > 0,
        "all_accepted": bool(n) and accepted == n,
        "mixed": bool(n) and 0 < accepted < n,
        "universal_term_count": len(universal),
        "note": "The candidate alignment is preserved whole. `valid: false` marks it, and never "
                "deletes it — a rejected answer is evidence about the model and discarding it "
                "would leave only the answers that happened to survive.",
    }
