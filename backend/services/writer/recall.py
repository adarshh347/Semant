"""
Semant Writer W9 — recall: the manuscript's memory of itself.

The render loop composes from the author's declared operators. This lets a passage also
rest on the author's OWN COMMITTED PROSE, which is the purest grounding in the system: an
operator is a declaration ABOUT prose, and a committed passage is prose the author already
stood behind and pushed through the Accept gate.

THE VERBATIM RULE — the load-bearing decision, and the reason this module imports no model.

The failure mode that would poison this is a recall that SUMMARISES: "you established the
room was cold, the sister estranged." That is fabrication wearing the author's canon. It
asserts as settled what the prose may have deliberately left ambiguous, and the author then
writes against a version of their book that the model invented — a corruption they have no
way to detect, because it arrives in the voice of their own manuscript.

So recall RETRIEVES AND STOPS. It returns the stored span, byte for byte, with where it
sits. It has no generation step, and the enforcement is structural rather than promised:

    THIS MODULE IMPORTS NO MODEL CLIENT. Not `llm_service`, not `role_registry`, nothing
    that could call out. There is no prompt in this file. A summary cannot leak out of a
    module that has nothing to summarise with, and a future edit that adds "just a short
    gloss" has to first add an import that a test forbids.

If the author wants a synthesis of prior material, that is a RENDER — declared, grounded,
quarantined, author-committed. Keeping the two apart is the whole discipline: the model may
point at what the author wrote; it may never tell the author what they said.

EMPTY IS AN HONEST ANSWER. A query that matches nothing returns nothing. That is the
retrieval analogue of W7's refusal-as-silence, and for the same reason: "you may have
established…" is worse than silence, because the author cannot tell it from a real memory.

──────────────────────────────────────────────────────────────────────────────────────────
ON RANKING, AND A DEVIATION FROM THE DIRECTIVE WORTH READING

§4 specifies pgvector. This repository has no Postgres and no text-embedding model: the
Writer is Groq-only by W1's constraint (Groq serves no embedding endpoint), and the only
embedding weights in the tree are FashionCLIP's — image-side, fashion-domain, 77-token
limit, and behind the ~2GB `requirements-ml.txt` that W1 explicitly excluded. Adding a
sentence-transformer to rank a few hundred paragraphs would be the largest dependency in
the Writer, imported for the least load-bearing part of it.

So ranking here is LEXICAL (BM25 over the project's committed prose), and the choice is
narrower than it sounds, because the gate does not turn on it. What W9 must guarantee is
that what comes back is the author's own words, unaltered, or nothing — and that guarantee
is independent of how the candidates were ordered. A worse ranker surfaces a less useful
paragraph; it cannot surface a paragraph the author never wrote. `score_spans` is isolated
precisely so a vector backend can replace it the day there is an honest text-embedding
story, without touching a line of the verbatim path.

The scan is O(corpus) per query, which is correct at manuscript scale (hundreds to low
thousands of paragraphs) and is the point at which an ANN index earns its keep — not
before.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.database import writer_passage_version_collection
from backend.services.manuscript_service import manuscript_service
from backend.services.writer import instrument

#: The instrumentation events. §8 — log now, analyse later.
RECALLED = "passage_recalled"
CITED = "passage_cited"

#: BM25's usual constants. Not tuned — tuning them would be optimising the half of this
#: module that the honesty rule does not depend on.
_K1 = 1.5
_B = 0.75

#: Words carrying no retrieval signal. Deliberately short and general: an aggressive list
#: would start deciding which of the AUTHOR's words matter, which is a small version of the
#: thing this module exists not to do.
_STOPWORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for from by with
was were is are be been being it its as had has have he she they them his her their i
""".split())

_WORD = re.compile(r"[a-z0-9']+")


class RecallError(ValueError):
    """A citation that cannot be honoured, with the reason."""


def tokens(text: str) -> List[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOPWORDS]


# ── the corpus: committed prose, current versions ───────────────────────────

async def committed_spans(
    project_id: str, *, include_historical: bool = False
) -> List[Dict[str, Any]]:
    """Every committed passage version this project can recall.

    CURRENT VERSIONS BY DEFAULT (§4). After W8 a lineage can hold several committed
    versions, and only one of them is in the book. Recalling a superseded version by
    default would ground new prose on words the author has already replaced — a subtler
    version of the same error as citing something they never accepted. Historical versions
    stay reachable, but only when the caller asks for them explicitly.
    """
    docs: List[Dict[str, Any]] = []
    async for doc in writer_passage_version_collection.find({"project_id": project_id}):
        docs.append(doc)

    if not include_historical:
        newest: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            key = doc.get("lineage_id")
            if key not in newest or doc.get("version", 0) > newest[key].get("version", 0):
                newest[key] = doc
        docs = list(newest.values())

    return sorted(docs, key=lambda d: (d.get("lineage_id", ""), d.get("version", 0)))


# ── ranking (replaceable; the verbatim path does not depend on it) ──────────

def score_spans(query: str, spans: Sequence[Dict[str, Any]]) -> List[Tuple[float, Dict]]:
    """BM25 over the spans' text. Pure — no I/O, no model, testable on its own."""
    q = tokens(query)
    if not q or not spans:
        return []

    docs = [tokens(s.get("text", "")) for s in spans]
    lengths = [len(d) for d in docs]
    avg = (sum(lengths) / len(lengths)) if lengths else 0.0
    counts = [Counter(d) for d in docs]

    df = Counter()
    for d in docs:
        for term in set(d):
            df[term] += 1

    n = len(docs)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for i, span in enumerate(spans):
        score = 0.0
        for term in q:
            f = counts[i].get(term, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            denom = f + _K1 * (1 - _B + _B * (lengths[i] / avg if avg else 1.0))
            score += idf * (f * (_K1 + 1)) / denom
        if score > 0:
            scored.append((score, span))

    return sorted(scored, key=lambda pair: (-pair[0], pair[1].get("lineage_id", "")))


# ── where a span sits, so the author can find it ────────────────────────────

async def _locate(span: Dict[str, Any]) -> Dict[str, Any]:
    """Chapter and scene titles for one span. Titles only — never a paraphrase of it."""
    scene_id = span.get("scene_id") or ""
    manuscript_id = span.get("manuscript_id") or ""
    scene = await manuscript_service.get_scene(scene_id) if scene_id else None
    chapter_title = ""
    if manuscript_id and scene_id:
        book = await manuscript_service.get_manuscript(manuscript_id)
        for chapter in (book or {}).get("chapters", []) or []:
            if scene_id in (chapter.get("scene_ids") or []):
                chapter_title = chapter.get("title", "")
                break
    return {
        "scene_id": scene_id,
        "scene_title": (scene or {}).get("title", ""),
        "chapter_title": chapter_title,
        "block_id": span.get("block_id", ""),
    }


# ── the actuator ────────────────────────────────────────────────────────────

async def recall(
    project_id: str,
    query: str,
    *,
    limit: int = 5,
    include_historical: bool = False,
) -> Dict[str, Any]:
    """The author's own committed sentences, ranked by relevance. Verbatim, or nothing.

    Returns `{query, spans, searched, truncated}`. Every `span["text"]` is the stored
    string, copied and not touched — `verbatim_violations` exists to say so under test, and
    the live proof asserts byte-equality against the ledger it came from.
    """
    corpus = await committed_spans(project_id, include_historical=include_historical)
    ranked = score_spans(query, corpus)[:max(0, limit)]

    spans: List[Dict[str, Any]] = []
    for score, doc in ranked:
        spans.append({
            "lineage_id": doc.get("lineage_id"),
            "version": doc.get("version"),
            "passage_id": doc.get("passage_id", ""),
            # THE AUTHOR'S WORDS, EXACTLY. Read from the ledger and handed on. Nothing in
            # this function trims, joins, truncates or ellipsises it: a "…" this module
            # added would be a sentence boundary the author did not write.
            "text": doc.get("text", ""),
            "score": round(score, 4),
            "provenance": doc.get("provenance", {}),
            "committed_at": doc.get("committed_at"),
            "location": await _locate(doc),
        })

    await instrument.record(
        RECALLED, project_id,
        extra={"query": query, "hits": len(spans), "searched": len(corpus),
               "historical": include_historical},
    )

    return {
        "query": query,
        "spans": spans,
        "searched": len(corpus),
        # An honest empty. The surface renders this as a result, not as a failure, and
        # there is deliberately nothing here for it to render instead.
        "empty_reason": ("" if spans else
                         "Nothing in your manuscript matches that." if corpus else
                         "There is no committed prose in this manuscript yet."),
    }


def verbatim_violations(
    spans: Sequence[Dict[str, Any]], ledger: Dict[Tuple[str, int], str]
) -> List[str]:
    """Any returned span whose text is not byte-equal to the ledger. Empty is the only pass.

    Exists so §2 is CHECKABLE rather than merely intended — the suite and the live proof
    both run it, and it is the assertion that would catch a well-meaning future edit that
    trimmed whitespace or clipped a long paragraph on the way out.
    """
    out: List[str] = []
    for span in spans:
        key = (span.get("lineage_id"), span.get("version"))
        stored = ledger.get(key)
        if stored is None:
            out.append(f"{key} is not in the ledger at all")
        elif stored != span.get("text"):
            out.append(f"{key} came back altered: {span.get('text', '')[:60]!r}")
    return out


# ── cite: grounding a render on committed canon only ────────────────────────

async def resolve_citations(
    project_id: str, refs: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Citation references → committed versions. Refuses anything that is not canon.

    INVARIANT 3, AT THE CITE DOOR. The two memories are the session (quarantined renders,
    which can still be dismissed) and the ledger (committed prose and the ontology). A
    citation may only reach into the ledger. Grounding a new passage on an unaccepted
    render would rest canon on something the author never accepted — and worse, on
    something they might then dismiss, leaving committed prose citing a passage that no
    longer exists anywhere.

    Refusing is the whole behaviour here. There is no fallback that quietly drops the bad
    reference and cites the rest: a citation list the author cannot trust to be complete
    is not an audit trail.
    """
    resolved: List[Dict[str, Any]] = []
    for ref in refs or []:
        if not isinstance(ref, dict):
            raise RecallError(f"a citation must name a passage, got {ref!r}")
        lineage_id = ref.get("lineage_id") or ""
        if not lineage_id:
            raise RecallError("a citation must name the passage lineage it cites")

        query: Dict[str, Any] = {"lineage_id": lineage_id, "project_id": project_id}
        version = ref.get("version")
        if version is not None:
            query["version"] = int(version)

        found = [d async for d in writer_passage_version_collection.find(query)]
        if not found:
            raise RecallError(
                f"cannot cite {lineage_id}"
                + (f"@v{version}" if version is not None else "")
                + ": there is no committed version of it. Only prose you have accepted "
                  "into the manuscript can be cited — a quarantined render is still yours "
                  "to dismiss, and canon cannot rest on something that might vanish."
            )
        doc = max(found, key=lambda d: d.get("version", 0))
        resolved.append({
            "lineage_id": doc["lineage_id"],
            "version": doc["version"],
            "passage_id": doc.get("passage_id", ""),
            "text": doc.get("text", ""),
            "scene_id": doc.get("scene_id", ""),
            "block_id": doc.get("block_id", ""),
        })
    return resolved


def as_grounding(cited: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Cited spans → what the render prompt shows: a label and the author's own text."""
    return [
        {"label": f"{c['lineage_id']}@v{c['version']}", "text": c.get("text", "")}
        for c in cited if (c.get("text") or "").strip()
    ]


def citation_stamps(cited: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """What provenance records (I4): which committed passages this one rested on."""
    return [
        {"lineage_id": c["lineage_id"], "version": c["version"],
         "passage_id": c.get("passage_id", "")}
        for c in cited
    ]
