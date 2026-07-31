"""
CIRCUIT-003 M6 — the external-knowledge retriever: the one producer that does not look.

Every other producer in Semant is evidence-bound: it reads the picture and reports what is
there. This one reads the LIBRARY. The benchmark needs claims the image cannot support —
Schinkel meant the Altes Museum as a civic temple; the building has a history — and no amount
of segmentation will ever yield them. They have to come from outside.

Letting knowledge in from outside is the single most dangerous thing this system can do, so
the entire module is built around one refusal:

    NO SOURCE → NO CLAIM.

That is the research twin of "no ground → no mark". It has teeth in four places, because a
guard in one place is a guard someone routes around:

  1. `Citation` cannot exist without a real url and title. Not "should have" — the constructor
     refuses.
  2. `SourcedStatement` cannot exist without a `Citation`, and its `epistemic_status` is a
     read-only property on a frozen object. There is no assignment that changes it.
  3. `SourcedStatement.from_document` requires the statement text to be a VERBATIM SPAN of the
     retrieved document. This is the anti-fabrication guard that matters most, and it is why
     no language model appears anywhere in this file: the claim is not summarised, paraphrased,
     or generated. It is quoted. A sentence that is not literally in the source cannot be
     constructed, so a fabricated citation has nothing to attach to.
  4. Retrieval that finds no document REFUSES rather than degrading. An unanswerable research
     question comes back empty with a reason, never with the model's best recollection.

WHY NO LLM HERE, stated plainly because its absence looks like an omission. Groq is available
in this process and could write a fluent paragraph about Schinkel from its weights alone. That
paragraph would be unfalsifiable, uncitable, and indistinguishable from a quoted one once it
is sitting in a descriptor next to a url. The whole value of `sourced` as a status is that a
reader can go and check. So: retrieval quotes, and nothing in this module writes prose.

THE PROVIDER SEAM. `SourceProvider` is a two-method protocol, so where the text comes from is
a deployment question rather than an architectural one:

  - `WikipediaProvider` — the live default. MediaWiki's API needs no key, returns real article
    text with a canonical url and a REVISION ID, which is what makes a citation reproducible: a
    quote is pinned to the revision it was taken from, so an article edited tomorrow does not
    silently rewrite what was cited today.
  - `CorpusProvider` — a curated local text corpus, read from a directory. Empty by default and
    entirely optional; it exists for deployments with no outbound network and for pinning a
    fixed reference set. It is NOT a fallback that invents anything — no corpus, no documents,
    and retrieval refuses exactly as it would with a network failure.

Tests inject their own provider. Nothing in the test suite touches the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from backend.services.epistemics import (EpistemicStatus, SOURCED_STATEMENT_TYPE,
                                         STATUS_KEY, EpistemicViolation)

# Retrieval outcomes. Same three-way distinction the actuator layer already draws, for the
# same reason: "the library is down" and "the library has nothing on this" call for different
# actions, and collapsing them would teach a curator to retry the one that will never succeed.
RETRIEVAL_OK = "ok"
RETRIEVAL_EMPTY = "empty"              # searched honestly, found nothing citable
RETRIEVAL_UNAVAILABLE = "unavailable"  # could not search at all

#: How much of the topic a sentence must carry to be quoted. Relevance, NOT truth — the
#: citation is what carries epistemic weight, and this number only decides whether a sentence
#: is ABOUT what was asked. Two of five topic terms clears it, which is what a sentence that
#: names the architect and the building looks like.
MIN_TERM_OVERLAP = 0.34

#: Words that carry no topic. Kept small on purpose: an aggressive stoplist would strip
#: "intent" or "civic" from a query where those are the entire question.
_STOPWORDS = frozenset("""
a an the of in on at to for from by with and or as is are was were be been being its it this
that these those he she they his her their what which who whom how why when where
""".split())

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")


def _digest(text: str) -> str:
    """A stable short id for a quotation. Content-addressed, so the same sentence from the
    same source always lands on the same `source_ref` and a re-run updates rather than duplicates."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


# ── what a source is ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Citation:
    """Where a claim came from, in enough detail that a reader can go and check.

    `url` and `title` are REQUIRED and validated in the constructor. A citation that cannot be
    followed is not a weak citation, it is decoration — and decoration next to a claim is
    exactly what makes a fabricated one look sound.

    `revision` pins the version quoted. Wikipedia's revid; whatever a corpus provides; None for
    a source with no versioning, which is honest and stays visible in the descriptor.
    """
    title: str
    url: str
    publisher: str
    source_id: str
    revision: Optional[str] = None
    retrieved_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not str(self.url or "").strip():
            raise EpistemicViolation("a citation needs a url — an unfollowable source is not a source")
        if not str(self.title or "").strip():
            raise EpistemicViolation("a citation needs a title")

    def as_dict(self) -> Dict[str, Any]:
        d = {"title": self.title, "url": self.url, "publisher": self.publisher,
             "source_id": self.source_id}
        if self.revision:
            d["revision"] = str(self.revision)
        if self.retrieved_at:
            d["retrieved_at"] = self.retrieved_at
        return d


@dataclass(frozen=True)
class SourceDocument:
    """One retrieved document: its text, and the citation any quote from it will carry."""
    citation: Citation
    text: str

    @property
    def title(self) -> str:
        return self.citation.title


@dataclass(frozen=True)
class SourcedStatement:
    """One claim from outside the image. NOT a percept, NOT a mark, and structurally unable to
    become either.

    The type distinction is the point. An image percept is a reading of pixels that a curator
    can argue with by looking harder; this is a quotation from a document, and the only way to
    argue with it is to read the document. Making them the same object would mean the whole
    system had to remember the difference. Making them different objects means it cannot forget.

    `epistemic_status` is a PROPERTY, not a field: there is no constructor argument for it, no
    setter, and the dataclass is frozen. `statement.epistemic_status = "visible"` raises
    `AttributeError` from Python itself, before any of this module's guards are consulted. That
    is the wall at its most literal.
    """
    text: str                       # a verbatim span of the source document
    citation: Citation
    confidence: float               # retrieval relevance, NOT a claim about truth
    topic: str = ""

    def __post_init__(self) -> None:
        if not str(self.text or "").strip():
            raise EpistemicViolation("a sourced statement with no text is not a statement")
        if not isinstance(self.citation, Citation):
            raise EpistemicViolation("a sourced statement requires a Citation")

    @property
    def epistemic_status(self) -> EpistemicStatus:
        """Always `sourced`. Read-only by construction — see the class docstring."""
        return EpistemicStatus.SOURCED

    @classmethod
    def from_document(cls, doc: SourceDocument, text: str, *, confidence: float,
                      topic: str = "") -> "SourcedStatement":
        """Quote a document. Refuses anything that is not literally in it.

        The substring check is the anti-fabrication guard: it makes "invent a plausible
        sentence and attach a real url" impossible, which is the failure mode a citation-bearing
        claim is otherwise most prone to.
        """
        quote = str(text or "").strip()
        if quote and quote not in doc.text:
            raise EpistemicViolation(
                f"refusing to attribute a statement that is not in the source: "
                f"{quote[:60]!r} does not appear in {doc.citation.url}")
        return cls(text=quote, citation=doc.citation, confidence=round(float(confidence), 3),
                   topic=topic)

    def to_descriptor(self, *, run_id: Optional[str], provider: str) -> Dict[str, Any]:
        """The quarantined descriptor shape — the same plain-JSON contract every producer emits.

        Deliberately geometry-free: a sourced statement has no extent, and a `geometry` of None
        is what stops any renderer from putting it on the image as though it did. It carries
        `citation` where a mark would carry provenance about a model, and its type is not one
        of the four mark types, so the Director's `_quarantined_marks()` cannot pick it up and
        hand it to `connect_marks` as evidence.
        """
        return {
            "producer": "historical_source",
            "type": SOURCED_STATEMENT_TYPE,
            "role": None,
            "label": self.text[:120],
            "statement": self.text,
            "topic": self.topic,
            # STABLE across processes and runs. `hash()` is salted per interpreter, so using it
            # here would give the same quotation a different ref on every retrieval — and the
            # circuit keys idempotency on `source_ref`, so a re-run would pile up duplicates
            # instead of updating the statement already under review.
            "source_ref": f"{self.citation.source_id}:{_digest(self.text)}",
            "geometry": None,                 # no extent — it is not on the image
            "linked_ground_ids": [],
            "citation": self.citation.as_dict(),
            "confidence": self.confidence,
            STATUS_KEY: EpistemicStatus.SOURCED.value,
            "provenance": {"run_id": run_id, "producer": "historical_source",
                           "adapter": provider, "model": None},
        }


@dataclass(frozen=True)
class RetrievalResult:
    """What a research call comes back with — including, explicitly, nothing.

    `queries_used` is every query actually issued, which is not always what the curator typed
    (see `_query_ladder`). It is reported rather than hidden: a reader comparing the topic they
    asked about with the queries that answered it is entitled to notice a gap between them.
    """
    status: str
    statements: Tuple[SourcedStatement, ...] = ()
    detail: str = ""
    provider: str = ""
    documents_seen: int = 0
    queries_used: Tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == RETRIEVAL_OK and bool(self.statements)


# ── the provider seam ────────────────────────────────────────────────────────

class SourceProvider(Protocol):
    """Where text comes from. Two methods, so a deployment can swap the library."""
    name: str

    def is_available(self) -> bool: ...

    def search(self, topic: str, *, limit: int = 3) -> Sequence[SourceDocument]: ...


class WikipediaProvider:
    """MediaWiki's public API. No key, real urls, and a revision id per article.

    One request per search (`generator=search` with `prop=extracts|info|revisions`), so a
    lookup is one round trip rather than a search followed by N fetches. Any network or shape
    failure raises, and the caller reports UNAVAILABLE — never an empty result, because
    "the library is unreachable" must not read as "there is nothing on this".
    """
    name = "wikipedia"
    API = "https://en.wikipedia.org/w/api.php"
    # Wikimedia's policy asks clients to identify themselves and gives them the right to block
    # ones that do not. A contactable UA is the price of a keyless API.
    USER_AGENT = "Semant/1.0 (perception research; +https://github.com/adarshh347/semant)"

    def __init__(self, *, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def is_available(self) -> bool:
        """Configured and importable. NOT a network probe — a reachability check on every
        availability question would put a round trip in front of every plan, and the fetch
        itself already reports failure honestly."""
        if os.getenv("EXTERNAL_SOURCE_DISABLED", "").strip().lower() in ("1", "true", "yes"):
            return False
        try:
            import requests  # noqa: F401
        except ImportError:
            return False
        return True

    def search(self, topic: str, *, limit: int = 3) -> Sequence[SourceDocument]:
        import requests
        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrsearch": topic, "gsrlimit": str(max(1, int(limit))),
            "prop": "extracts|info|revisions", "explaintext": "1",
            "inprop": "url", "rvprop": "ids",
        }
        resp = requests.get(self.API, params=params, timeout=self.timeout,
                            headers={"User-Agent": self.USER_AGENT})
        resp.raise_for_status()
        pages = ((resp.json() or {}).get("query") or {}).get("pages") or []
        retrieved_at = datetime.now(timezone.utc).isoformat()
        out: List[SourceDocument] = []
        for page in pages:
            text = str(page.get("extract") or "").strip()
            url = str(page.get("fullurl") or "").strip()
            title = str(page.get("title") or "").strip()
            if not text or not url or not title:
                continue                      # a page with no extract is nothing to quote
            revisions = page.get("revisions") or []
            revid = str(revisions[0].get("revid")) if revisions else None
            out.append(SourceDocument(
                text=text,
                citation=Citation(title=title, url=url, publisher="Wikipedia",
                                  source_id=f"wikipedia:{page.get('pageid')}",
                                  revision=revid, retrieved_at=retrieved_at)))
        return out


class CorpusProvider:
    """A curated local corpus. Offline, deterministic, and empty unless someone fills it.

    Each entry is a JSON file: `{"title": ..., "url": ..., "publisher": ..., "text": ...}`. The
    url is still mandatory — a local copy of a document still has to say where the document
    came from, or the quote is uncheckable and the citation is decoration again.

    Ships with NO documents. It is a seam for network-isolated deployments, not a place to
    stash answers for the benchmark.
    """
    name = "corpus"

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = root or os.getenv("EXTERNAL_SOURCE_CORPUS", "").strip()

    def is_available(self) -> bool:
        return bool(self.root) and os.path.isdir(self.root)

    def search(self, topic: str, *, limit: int = 3) -> Sequence[SourceDocument]:
        if not self.is_available():
            return []
        terms = _topic_terms(topic)
        scored: List[Tuple[float, SourceDocument]] = []
        for entry in sorted(os.listdir(self.root)):
            if not entry.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.root, entry), "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                doc = SourceDocument(
                    text=str(raw.get("text") or ""),
                    citation=Citation(title=str(raw.get("title") or ""),
                                      url=str(raw.get("url") or ""),
                                      publisher=str(raw.get("publisher") or "corpus"),
                                      source_id=f"corpus:{entry}",
                                      revision=raw.get("revision")))
            except (OSError, ValueError, EpistemicViolation):
                continue                      # a malformed entry is skipped, never guessed at
            if not doc.text:
                continue
            haystack = f"{doc.title} {doc.text}".lower()
            score = sum(1 for t in terms if t in haystack) / max(1, len(terms))
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scored[:limit]]


def default_provider() -> SourceProvider:
    """The live provider. A configured corpus wins — a deployment that pinned its reference
    set meant it — otherwise Wikipedia."""
    corpus = CorpusProvider()
    if corpus.is_available():
        return corpus
    return WikipediaProvider()


# ── quoting ──────────────────────────────────────────────────────────────────

def _topic_terms(topic: str) -> List[str]:
    """The words of a topic that actually select for it, lowercased."""
    return [w.lower() for w in _WORD.findall(topic or "")
            if w.lower() not in _STOPWORDS and len(w) > 2]


def _ranked_terms(topic: str) -> List[str]:
    """The topic's terms, most selective first.

    Capitalisation is the signal, because a curator writing a topic capitalises the things
    that NAME the subject: in "Schinkel Altes Museum civic intent", the proper nouns identify
    the building and the architect while "civic intent" says what about them is being asked.
    Original order is preserved within each group, so a relaxed query still reads like the
    thing it came from rather than a bag of words.
    """
    words = _WORD.findall(topic or "")
    proper = [w.lower() for w in words if w[:1].isupper() and w.lower() not in _STOPWORDS
              and len(w) > 2]
    common = [w.lower() for w in words if not w[:1].isupper() and w.lower() not in _STOPWORDS
              and len(w) > 2]
    ordered, seen = [], set()
    for w in proper + common:
        if w not in seen:
            seen.add(w)
            ordered.append(w)
    return ordered


def _query_ladder(topic: str, *, floor: int = 2) -> List[str]:
    """The curator's exact words first, then progressively less demanding queries.

    WHY THIS EXISTS. MediaWiki's search is conjunctive: every term must appear. A research
    topic is written in natural language — "Schinkel Altes Museum civic intent" — and asking a
    library for the shelf containing all five of those words returns nothing, while the article
    that answers the question sits one term away. Without relaxation the actuator would refuse
    almost every real question, which is a refusal that teaches nothing.

    WHAT IT DOES NOT DO. Relaxation chooses which SHELF to look on. It never touches what is
    claimed: statements are still filtered for relevance against the FULL topic, still quoted
    verbatim, and still carry the citation of the document they came from. A looser query
    cannot produce a looser claim.

    The floor of two terms is what keeps nonsense unanswerable. Descending to a single common
    word would find *some* article for any input at all, and "found a document" would stop
    meaning anything.
    """
    rungs = [str(topic or "").strip()]
    terms = _ranked_terms(topic)
    for n in range(len(terms), max(floor, 1) - 1, -1):
        rung = " ".join(terms[:n])
        if rung and rung not in rungs:
            rungs.append(rung)
    return [r for r in rungs if r]


#: Sections that are APPARATUS rather than claims. A bibliography line ("Jörg Trempler: Das
#: Wandbildprogramm von Karl Friedrich Schinkel, Altes Museum Berlin.") is short, dense with
#: the topic's terms, and therefore ranks near the top of any term-overlap scoring — while
#: asserting nothing at all. Skipping these sections is the difference between quoting what a
#: source SAYS and quoting what it CITES.
_APPARATUS_SECTIONS = frozenset({
    "further reading", "bibliography", "references", "external links", "see also",
    "notes", "sources", "literature", "gallery", "footnotes", "citations", "works cited",
})

_HEADING = re.compile(r"^=+\s*(?P<title>.*?)\s*=+$")


def _sentences(text: str) -> List[str]:
    """Quotable sentences of a document, each a verbatim contiguous span of it.

    Splits per paragraph so a sentence never straddles a section break, tracks the MediaWiki
    section it is in, and skips the apparatus sections entirely. Every returned string is `in`
    the original text — `SourcedStatement.from_document` re-checks that, but the splitter must
    not be the thing that breaks it.
    """
    out: List[str] = []
    in_apparatus = False
    for para in (text or "").split("\n"):
        para = para.strip()
        if not para:
            continue
        heading = _HEADING.match(para)
        if heading:
            in_apparatus = heading.group("title").strip().lower() in _APPARATUS_SECTIONS
            continue                          # a heading is a label, not a claim
        if in_apparatus:
            continue
        for sentence in _SENTENCE_SPLIT.split(para):
            sentence = sentence.strip()
            if len(sentence) < 40 or not sentence.endswith((".", "!", "?")):
                continue                      # fragments and list items are not claims
            out.append(sentence)
    return out


def _score(sentence: str, terms: Sequence[str]) -> float:
    if not terms:
        return 0.0
    low = sentence.lower()
    return sum(1 for t in terms if t in low) / len(terms)


def statements_from_documents(docs: Sequence[SourceDocument], topic: str, *,
                              max_statements: int = 5,
                              min_overlap: float = MIN_TERM_OVERLAP) -> List[SourcedStatement]:
    """Quote the sentences of these documents that are actually about the topic.

    Ranked across ALL documents rather than per document, so three weak sentences from the
    top hit do not crowd out the one strong sentence from the second.
    """
    terms = _topic_terms(topic)
    scored: List[Tuple[float, SourceDocument, str]] = []
    for doc in docs:
        for sentence in _sentences(doc.text):
            score = _score(sentence, terms)
            if score >= min_overlap:
                scored.append((score, doc, sentence))
    # Relevance first; among equally relevant sentences prefer the LONGER one. At equal term
    # overlap the short sentence is usually a fragment or an aside and the long one is the
    # sentence doing the actual explaining.
    scored.sort(key=lambda triple: (-triple[0], -len(triple[2])))
    out: List[SourcedStatement] = []
    seen: set = set()
    for score, doc, sentence in scored:
        if sentence in seen:
            continue
        seen.add(sentence)
        out.append(SourcedStatement.from_document(doc, sentence, confidence=score, topic=topic))
        if len(out) >= max_statements:
            break
    return out


def retrieve(topic: str, *, provider: Optional[SourceProvider] = None,
             max_statements: int = 5, limit: int = 3) -> RetrievalResult:
    """Look a topic up and come back with quotations, or with a reason there are none.

    The three outcomes are kept apart on purpose (see the RETRIEVAL_* constants). Note that an
    empty topic is UNAVAILABLE-adjacent but reported as EMPTY with an explicit reason: there
    was nothing to look up, which is a refusal the caller caused, not one the library did.
    """
    prov = provider or default_provider()
    name = getattr(prov, "name", "unknown")
    if not str(topic or "").strip():
        return RetrievalResult(status=RETRIEVAL_EMPTY, provider=name,
                               detail="no topic to research")
    if not prov.is_available():
        return RetrievalResult(status=RETRIEVAL_UNAVAILABLE, provider=name,
                               detail=f"source provider '{name}' is unavailable")
    # Descend the ladder ACCUMULATING documents rather than stopping at the first rung that
    # returns anything. Stopping early makes the shelf arbitrary: the narrowest rung that
    # happens to match may hit one tangential article while the rung below it holds the three
    # that actually cover the subject. Gathering until there are `limit` distinct documents
    # costs a couple of extra lookups and lets `statements_from_documents` rank across the
    # whole shelf, which is where the ranking belongs.
    docs: List[SourceDocument] = []
    queries: List[str] = []
    seen_sources: set = set()
    for rung in _query_ladder(topic):
        if len(docs) >= limit:
            break
        queries.append(rung)
        try:
            found = list(prov.search(rung, limit=limit) or [])
        except Exception as e:
            # A failed lookup is UNAVAILABLE, never EMPTY. The difference is whether a curator
            # should try again, and reporting "nothing found" for a timeout would be a lie
            # about the library's contents.
            return RetrievalResult(status=RETRIEVAL_UNAVAILABLE, provider=name,
                                   queries_used=tuple(queries),
                                   detail=f"lookup failed: {type(e).__name__}: {e}")
        for doc in found:
            if doc.citation.source_id in seen_sources:
                continue
            seen_sources.add(doc.citation.source_id)
            docs.append(doc)
    if not docs:
        return RetrievalResult(status=RETRIEVAL_EMPTY, provider=name, queries_used=tuple(queries),
                               detail=f"no source found for '{topic}'")
    statements = statements_from_documents(docs, topic, max_statements=max_statements)
    relaxed = [q for q in queries if q != str(topic or "").strip()]
    asked = f" (searched {', '.join(repr(q) for q in relaxed)})" if relaxed else ""
    if not statements:
        return RetrievalResult(status=RETRIEVAL_EMPTY, provider=name, documents_seen=len(docs),
                               queries_used=tuple(queries),
                               detail=f"{len(docs)} source(s) found, none stating anything "
                                      f"specific to '{topic}'{asked}")
    return RetrievalResult(status=RETRIEVAL_OK, statements=tuple(statements), provider=name,
                           documents_seen=len(docs), queries_used=tuple(queries),
                           detail=f"{len(statements)} sourced statement(s) from "
                                  f"{len(docs)} source(s){asked}")
