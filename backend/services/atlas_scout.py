"""
ATLAS T2 — the Scout: where to POINT the comparison, never what the comparison says.

THE DISCIPLINE, WHICH IS THE WHOLE GATE. A language model reading a corpus will happily tell you
that the façade prepares the rotunda. It has no access to either photograph, no marks, and no way
to check — so that sentence is an associative hunch dressed as a finding, and it is exactly the
fabrication this system is built to refuse. T2 therefore takes the hunch as the RAW SIGNAL and
never as the discriminator, the same shape as everywhere else in Semant:

    the Scout proposes a PAIR       →  `compare_views` (C3) decides whether a relation grounds
    (a hypothesis, uncommitted)        (the orthogonal discriminator, unchanged by this module)
                                    →  the human confirms

The Scout is plan mode for edges. It says "these two might be worth comparing, and here is why I
thought so"; it never says two images ARE related. A candidate is not an edge, is not a percept,
is not persisted, and cannot become one except by going through the gate.

WHAT THIS MODULE MAY NOT DO, enforced in code rather than asked for in a prompt (a prompt is a
request; these are the fence):

  1. IT MAY NOT NAME THE RELATION. `{from, to, rationale}` is the entire vocabulary. If the model
     returns `role`, `relation`, `epistemic`, `confidence` or geometry, those keys are DROPPED and
     the drop is reported. Naming the relation belongs to `compare_views`, which looks at marks;
     accepting a name here would let the model's wording arrive on the canvas as though a
     comparison had been run.

  2. IT MAY NOT INVENT AN IMAGE. A candidate naming a node this Atlas does not hold is dropped and
     reported. The Scout suggests where to point an instrument that exists, at images already on
     the canvas — a suggestion about something off-canvas is not actionable and, worse, would read
     as evidence that an unseen image belongs in the corpus.

  3. IT MAY NOT PERSIST ANYTHING. There is no write in this module and no route that calls it
     writes. Candidates live in the session. A test greps for it.

  4. DROPS ARE REPORTED, NEVER SILENT. Following `groq_planner`'s guard: filtering quietly would
     hide how often the model invents nodes or tries to name relations, and that count is the
     observable that tells a reader whether to trust the Scout at all.

FAILURE IS "UNAVAILABLE", AND SAID OUT LOUD. No key, no client, an API error, unparseable JSON —
each returns a refusal naming which, rather than an empty candidate list. An empty list means "the
model read your corpus and found nothing worth comparing", which is a real and useful answer; a
silent empty list on a dead API would be a lie told in the same words.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.services import role_registry

SCOUT_CONTRACT_VERSION = 1

#: ROLES-001 — the Scout is a THINKER. It reads a corpus description and proposes where to look;
#: it never authors geometry and never measures. Its ceiling is `interpretive`, and even that
#: overstates a candidate: a candidate asserts nothing at all until the gate has run.
ROLE = "relation_scout"

#: A canvas is for thinking on. Twenty ghost lines over six images is a cobweb nobody can read, and
#: it would also mean the Scout was guessing rather than proposing.
MAX_CANDIDATES = 8
MAX_RATIONALE_CHARS = 240

#: The ONLY keys a candidate may carry. A whitelist, not a blacklist — the dict is BUILT from these
#: three fields rather than edited down from what arrived, so a key nobody thought of has no path in.
CANDIDATE_KEYS = ("from", "to", "rationale")

# Why the Scout as a whole could not run. A closed set, like `plan.py`'s.
REFUSED_TOO_FEW_IMAGES = "too_few_images"        # one image cannot be compared with itself
REFUSED_MODEL_UNAVAILABLE = "model_unavailable"  # no key, no client, API error, unparseable reply
REFUSED_NOTHING_PROPOSED = "nothing_proposed"    # it ran and proposed nothing it was allowed to

# Why one candidate did not survive. Reported, never silently dropped.
DROPPED_UNKNOWN_NODE = "unknown_node"        # named an image this Atlas does not hold
DROPPED_SAME_NODE = "same_node"              # an image is not related to itself
DROPPED_NO_RATIONALE = "no_rationale"        # a pair with no "why" is a coin toss, not a proposal
DROPPED_DUPLICATE = "duplicate"              # the same pair twice
DROPPED_ALREADY_DRAWN = "already_drawn"      # the writer has already grounded this pair
DROPPED_NAMED_A_RELATION = "named_a_relation"  # tried to assert what the comparison decides


def refusal(reason: str, detail: str) -> Dict[str, Any]:
    return {"reason": reason, "detail": detail}


def dropped(reason: str, detail: str, **extra: Any) -> Dict[str, Any]:
    out = {"reason": reason, "detail": detail}
    out.update(extra)
    return out


# ── what the model is allowed to see ─────────────────────────────────────────

def _mark_words(post: Optional[Mapping[str, Any]]) -> List[str]:
    """The LABELS of what has been committed on an image. Words only — never geometry.

    The Scout reasons about a corpus in language, so it gets language: what the curator has already
    named on each picture. It does not get masks, boxes, points or fields, because a model handed
    coordinates starts describing what it "sees" in them, and it sees nothing. Withholding the
    geometry is not a token optimisation; it removes the material a fabrication would be built from.
    """
    from backend.services.atlas_relation import committed_marks

    words: List[str] = []
    for mark in committed_marks(post):
        label = str(mark.get("label") or mark.get("role") or "").strip()
        if label:
            words.append(label[:60])
    for ground in (post or {}).get("grounds") or []:
        if not isinstance(ground, Mapping):
            continue
        if str(ground.get("source") or "user") == "model_suggested":
            continue
        label = str(ground.get("label") or ground.get("role") or "").strip()
        if label:
            words.append(label[:60])
    # Order kept, repeats collapsed: "three regions all called sky" is one fact about the image.
    return list(dict.fromkeys(words))[:12]


def scout_material(doc: Mapping[str, Any],
                   posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The corpus, as the Scout is permitted to know it: node id, title, and committed words.

    An unreadable image is INCLUDED, marked unreadable and with no words. Dropping it would let the
    model propose around a hole it cannot see, and the resulting candidates would quietly assume a
    corpus smaller than the one on screen.
    """
    out: List[Dict[str, Any]] = []
    for node in doc.get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        post_id = str(node.get("post_id") or "")
        post = posts.get(post_id)
        out.append({
            "node_id": str(node.get("node_id") or ""),
            "title": str((post or {}).get("instagram_handle")
                         or (post or {}).get("domain") or "") if post else "",
            "readable": post is not None,
            "committed": _mark_words(post),
        })
    return out


def drawn_pairs(doc: Mapping[str, Any]) -> Set[frozenset]:
    """The pairs a relation has already been grounded between. Unordered: a second edge the other
    way round is a different claim to make BY HAND, not something to suggest again."""
    out: Set[frozenset] = set()
    for edge in doc.get("edges") or []:
        if not isinstance(edge, Mapping):
            continue
        a, b = str(edge.get("source_node") or ""), str(edge.get("target_node") or "")
        if a and b:
            out.add(frozenset((a, b)))
    return out


# ── what comes back, and what is allowed through ─────────────────────────────

def parse_candidates(payload: Any, *, allowed: Sequence[str],
                     already: Optional[Set[frozenset]] = None,
                     limit: int = MAX_CANDIDATES) -> Tuple[List[Dict[str, Any]],
                                                           List[Dict[str, Any]]]:
    """The model's reply → `(candidates, dropped)`. Pure: no model, no database, no clock.

    This function is the fence. Everything the Scout is not allowed to do is refused here, by name,
    with the drop recorded — so the guards are testable without a network and visible when they
    fire. A candidate that survives carries three keys and asserts nothing beyond "these two, and
    here is the hunch".
    """
    known = {str(n) for n in allowed}
    seen: Set[frozenset] = set()
    already = already or set()
    kept: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    items = payload.get("candidates") if isinstance(payload, Mapping) else payload
    if not isinstance(items, (list, tuple)):
        return [], [dropped("unparseable", "the reply carried no list of candidates")]

    for raw in items:
        if not isinstance(raw, Mapping):
            drops.append(dropped("unparseable", "a candidate was not an object"))
            continue

        a = str(raw.get("from") or raw.get("source") or "").strip()
        b = str(raw.get("to") or raw.get("target") or "").strip()
        rationale = str(raw.get("rationale") or raw.get("why") or "").strip()

        # GUARD 1 — it may not name the relation. Checked before anything else, because a candidate
        # that tried is worth reporting even if it would have been dropped for another reason too.
        asserted = sorted(k for k in raw.keys()
                          if k in ("role", "relation", "relation_role", "epistemic",
                                   "epistemic_status", "confidence", "score", "geometry",
                                   "mask", "box", "spans", "mark_id"))
        if asserted:
            drops.append(dropped(
                DROPPED_NAMED_A_RELATION,
                f"a candidate carried {asserted} — naming the relation is the comparison's job",
                **{"from": a, "to": b}))
            continue

        if a not in known or b not in known:
            missing = [n for n in (a, b) if n not in known]
            drops.append(dropped(
                DROPPED_UNKNOWN_NODE,
                f"this Atlas holds no node {', '.join(missing) or '(unnamed)'}",
                **{"from": a, "to": b}))
            continue
        if a == b:
            drops.append(dropped(DROPPED_SAME_NODE,
                                 "an image is not related to itself", **{"from": a, "to": b}))
            continue
        if not rationale:
            # A pair with no "why" cannot be judged by the writer before they spend a model run on
            # it, which is the only thing a candidate is FOR.
            drops.append(dropped(DROPPED_NO_RATIONALE,
                                 "a candidate with no reason is a coin toss",
                                 **{"from": a, "to": b}))
            continue

        pair = frozenset((a, b))
        if pair in already:
            drops.append(dropped(DROPPED_ALREADY_DRAWN,
                                 "a relation is already drawn between these two",
                                 **{"from": a, "to": b}))
            continue
        if pair in seen:
            drops.append(dropped(DROPPED_DUPLICATE, "the same pair was proposed twice",
                                 **{"from": a, "to": b}))
            continue

        seen.add(pair)
        # BUILT from three known fields, never edited down from what arrived.
        kept.append({"from": a, "to": b, "rationale": rationale[:MAX_RATIONALE_CHARS]})
        if len(kept) >= limit:
            break

    return kept, drops


# ── the model, behind a seam ─────────────────────────────────────────────────

PROMPT = """You are looking at a writer's Atlas: several photographs on one canvas, each with the \
words its curator has already committed to it.

Propose pairs of images that might be worth COMPARING, and say why you think so in one line.

Rules you must follow:
- Only use the node_id values listed below. Never invent an image.
- Never state that two images ARE related, and never name the relation. A separate instrument \
looks at the actual evidence and decides that; you are only saying where to point it.
- Your rationale is a hunch about why the pair might repay comparison, phrased as a hypothesis.
- If nothing is worth comparing, return an empty list. That is a real answer.

Return JSON: {"candidates": [{"from": "<node_id>", "to": "<node_id>", "rationale": "<one line>"}]}

The canvas:
"""


class RelationScout:
    """The Groq-backed proposer, behind the same kind of seam as `GroqPlanner`.

    One call per `propose`. No re-prompt loop: asking again until something parses would search for
    a reply that survives the fence rather than a reply that is honest, which is the fabrication
    this layer exists to prevent arriving one level up.
    """

    name = "relation_scout"

    def __init__(self, client: Any = None, model: Optional[str] = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        self.last_error = ""

    @property
    def model(self) -> str:
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

    def available(self) -> bool:
        return self._get_client() is not None

    def propose(self, material: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
        """The raw reply, or None with `last_error` set. Parsing and judging happen elsewhere."""
        self.last_error = ""
        client = self._get_client()
        if client is None:
            self.last_error = "no Groq client configured (GROQ_API_KEY unset)"
            return None
        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user",
                           "content": PROMPT + json.dumps(list(material), indent=2)}],
                response_format={"type": "json_object"},
                temperature=0.4,
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:                       # noqa: BLE001 — every failure is "unavailable"
            self.last_error = str(e)[:200]
            return None


# ── the gesture ──────────────────────────────────────────────────────────────

def propose_relations(doc: Mapping[str, Any], posts: Mapping[str, Mapping[str, Any]], *,
                      scout: Optional[RelationScout] = None,
                      limit: int = MAX_CANDIDATES) -> Dict[str, Any]:
    """Suggest where a comparison might be worth running. Returns candidates, or a refusal.

    WRITES NOTHING, and could not: it is handed a document and a dict of posts and returns a plain
    structure. The candidates it returns are session material. The only way one becomes an edge is
    for the writer to confirm it, which calls C3's `compare_views` path — a different module, a
    different route, and the only place in the Atlas that may mint a relation.
    """
    material = scout_material(doc, posts)
    if len([m for m in material if m["readable"]]) < 2:
        return {"refused": refusal(
            REFUSED_TOO_FEW_IMAGES,
            "a comparison needs two readable images; this Atlas has fewer")}

    scout = scout or RelationScout()
    payload = scout.propose(material)
    if payload is None:
        # Named, not swallowed. An empty list would say "nothing worth comparing", which is a
        # different and much stronger claim than "the model could not be reached".
        return {"refused": refusal(
            REFUSED_MODEL_UNAVAILABLE,
            scout.last_error or "the relation scout could not be reached")}

    candidates, drops = parse_candidates(
        payload, allowed=[m["node_id"] for m in material],
        already=drawn_pairs(doc), limit=limit)

    if not candidates:
        return {"refused": refusal(
            REFUSED_NOTHING_PROPOSED,
            "the scout proposed nothing it was allowed to propose"),
            "dropped": drops}

    return {"candidates": candidates, "dropped": drops,
            "contract_version": SCOUT_CONTRACT_VERSION}
