"""
CIRCUIT-003 M4 — the article resolver: a citation becomes a LIVE percept.

M3's `ArticleDraft` cites evidence by `step_id`: the id of the plan step that was supposed to
produce it. That is the right key for an argument — it survives re-planning and it is what M2's
lineage is keyed on — and it is not, by itself, something a renderer can draw. To draw the percept
the reader is looking at, the article needs the GEOMETRY that was actually produced, and the image
it was produced on.

This module is that join, and it is READ-ONLY: it reads a draft, the run's quarantined
suggestions, and M1's corpus, and returns what to draw. It produces nothing, commits nothing, and
mutates nothing it is handed.

THE JOIN IS A LOOKUP NOW — AND THE WEAK KEY IS STILL HERE, ON PURPOSE.

As shipped, M4 could not do a lookup. A produced suggestion carried `provenance: {run_id,
producer, adapter}` and NOT the step id of the plan step that caused it, so `step_id → suggestion`
had to be approximated by what both sides did record: the actuator that ran, and the image it ran
on. Two `pressure_zone` steps on one image were indistinguishable from here.

PROV-001 Seam 1 closed that at the source: `real_actuators._stamp_step_id` now writes
`provenance.step_id` at the single chokepoint every producer passes through. When a citation and
a suggestion both name a step, this module joins on identity and the approximation is never
consulted.

The weak key REMAINS, and deleting it would be a bug. Every suggestion produced before that change
carries no step_id — for those it is not a worse key, it is the only key. So the order is: exact
first, approximate only when the exact key is absent on both sides.

When the approximation genuinely cannot decide, this module REFUSES to pick. An article that
silently drew the wrong field beside a sentence would be the most damaging possible failure in
this whole stack: the prose would be true, the citation would be real, and the picture would be of
something else. Every reader would believe it, and nothing in the document would be wrong enough
to notice.

So a citation resolves to exactly one percept, or it resolves to nothing and says which of the two
happened:

    RESOLVED    — one match. Geometry and source image travel with it.
    UNPRODUCED  — no suggestion matches. The step ran (M3 only composes from confirmed runs) but
                  left no drawable geometry, or the quarantine handed here does not contain it.
    AMBIGUOUS   — more than one match. The candidates are reported; none is chosen.

AMBIGUOUS now has two distinct causes and says which it hit. Down the weak-key path the producing
step is unknown (historical data). Down the exact path the step is known and produced several
drawable percepts, and the citation does not say which one the sentence meant — a modelling
question, not a provenance gap. The detail text distinguishes them so a reader is not sent to fix
something that is already fixed.

The honest-defect channel M3 built (`uncited_mentions`, `relevance_flags`) is carried through
untouched, because M4's whole job is to make those visible rather than let them die in a dict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .corpus import CorpusWorkingMemory
from .memory import WorkingMemory

RESOLVER_VERSION = 1

# How a citation resolved. Closed set — the renderer branches on these.
RESOLVED = "resolved"
UNPRODUCED = "unproduced"
AMBIGUOUS = "ambiguous"

# Descriptor types that carry drawable extent. A percept draft and a sourced statement do not:
# they rest on things that do, and drawing a box for them would invent an extent nobody produced.
DRAWABLE_TYPES = ("region_mask", "brush_field", "trace_mark", "relation_mark")


@dataclass(frozen=True)
class ResolvedCitation:
    """One citation, joined to what was actually produced for it.

    `geometry` is the produced geometry verbatim — the SAME dict the Differential's renderers
    already draw. It is deliberately not reshaped here: a second geometry format would be a second
    thing to keep aligned with the overlays, and alignment is the one property this whole stack
    cannot afford to get subtly wrong.
    """
    step_id: str
    actuator: str
    function: str
    epistemic: str
    status: str                      # RESOLVED | UNPRODUCED | AMBIGUOUS
    image: Optional[str] = None      # the corpus post id
    image_ref: str = ""              # the source image URL — what the renderer draws ON
    image_title: str = ""
    attribution: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    geometry_kind: str = ""
    label: str = ""
    source_ref: str = ""
    detail: str = ""                 # why, when not resolved
    candidates: Tuple[str, ...] = () # the ambiguous set, named rather than silently narrowed

    @property
    def drawable(self) -> bool:
        return self.status == RESOLVED and bool(self.geometry)

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "actuator": self.actuator, "function": self.function,
                "epistemic": self.epistemic, "status": self.status, "image": self.image,
                "image_ref": self.image_ref, "image_title": self.image_title,
                "attribution": self.attribution, "geometry": self.geometry,
                "geometry_kind": self.geometry_kind, "label": self.label,
                "source_ref": self.source_ref, "detail": self.detail,
                "candidates": list(self.candidates), "drawable": self.drawable,
                # What a click needs to reopen this percept on its source image.
                "reopen": ({"post_id": self.image, "source_ref": self.source_ref,
                            "step_id": self.step_id} if self.image else None)}


def _post_id_of(suggestion: Dict[str, Any]) -> Optional[str]:
    """Which image a quarantined suggestion was produced on.

    M1 tags each per-image suggestion with `post_id` on the way out of the corpus context; a
    single-post run has it on the provenance instead. Both are checked, and neither is guessed.
    """
    direct = suggestion.get("post_id")
    if direct:
        return str(direct)
    prov = suggestion.get("provenance") or {}
    if prov.get("post_id"):
        return str(prov["post_id"])
    spans = (suggestion.get("corpus") or {}).get("spans") or []
    if len(spans) == 1:
        return str(spans[0])
    return None


def _produced_by(suggestion: Dict[str, Any]) -> Tuple[str, ...]:
    """Every name this suggestion could be matched on: the adapter that ran and the producer it
    was minted as. Both, because they diverge — `compare_views` mints under the frozen
    `semantic_read` producer vocabulary while its adapter records what actually ran."""
    prov = suggestion.get("provenance") or {}
    names = [prov.get("adapter"), prov.get("producer"), suggestion.get("producer")]
    return tuple(dict.fromkeys(str(n) for n in names if n))


def _step_id_of(suggestion: Dict[str, Any]) -> str:
    """The plan step that produced this suggestion, or "" when it does not record one.

    PROV-001. `real_actuators._stamp_step_id` writes this at the produce chokepoint, so anything
    made by a run on this code carries it. Anything made BEFORE it does not, and "" is how that
    says so — the resolver reads the absence and falls back rather than treating a missing step
    as a step named "".
    """
    prov = suggestion.get("provenance") or {}
    if not isinstance(prov, dict):
        return ""
    return str(prov.get("step_id") or "")


def _matches_step(suggestion: Dict[str, Any], step_id: str) -> bool:
    """Exact identity match: this suggestion was produced BY that plan step."""
    if suggestion.get("type") not in DRAWABLE_TYPES:
        return False
    return bool(step_id) and _step_id_of(suggestion) == step_id


def _matches(suggestion: Dict[str, Any], actuator: str, image: Optional[str]) -> bool:
    if suggestion.get("type") not in DRAWABLE_TYPES:
        return False
    if actuator not in _produced_by(suggestion):
        return False
    if image is None:
        return True
    produced_on = _post_id_of(suggestion)
    # A cross-image relation belongs to every image it spans, so a citation on either side of a
    # comparison finds it.
    spans = [str(s) for s in ((suggestion.get("corpus") or {}).get("spans") or [])]
    if spans:
        return image in spans
    return produced_on is None or produced_on == image


def _image_meta(memory: WorkingMemory, post_id: Optional[str]) -> Tuple[str, str]:
    """(image_ref, title) for a corpus image. The image_ref is what the renderer draws on."""
    if not post_id:
        return "", ""
    if isinstance(memory, CorpusWorkingMemory) and memory.corpus is not None:
        image = memory.corpus.by_post_id(post_id)
        if image is not None:
            return (image.image_ref or ""), (image.title or "")
    if getattr(memory, "post_id", None) == post_id:
        return memory.image_ref or "", ""
    return "", ""


def resolve_citation(citation: Dict[str, Any], suggestions: Sequence[Dict[str, Any]],
                     memory: WorkingMemory) -> ResolvedCitation:
    """One citation → the live percept produced for it, or an honest non-answer."""
    step_id = str(citation.get("step_id") or "")
    actuator = str(citation.get("actuator") or "")
    image = citation.get("image")
    image_ref, title = _image_meta(memory, image)
    base = dict(
        step_id=step_id, actuator=actuator,
        function=str(citation.get("function") or ""),
        epistemic=str(citation.get("epistemic") or ""),
        image=image, image_ref=image_ref or str(citation.get("image_ref") or ""),
        image_title=title or str(citation.get("image_title") or ""),
        attribution=citation.get("attribution"))

    # PROV-001 — the exact join, tried first.
    #
    # A citation names the step that was meant to produce its evidence; since Seam 1 the
    # suggestion names the step that did. When both are present this is an identity lookup, and
    # the (actuator, image) approximation below — with everything it cannot distinguish — is
    # never reached. Two `pressure_zone` steps on one image now resolve to their own percepts.
    #
    # The fallback is NOT dead code and must not be deleted: every suggestion produced before
    # this change carries no step_id, and for those the weak key is still the only key there is.
    # Its AMBIGUOUS refusal therefore stays reachable, and stays correct, for historical data.
    by_step = [s for s in suggestions if isinstance(s, dict) and _matches_step(s, step_id)]
    matched = by_step or [
        s for s in suggestions if isinstance(s, dict) and _matches(s, actuator, image)]

    if not matched:
        return ResolvedCitation(
            status=UNPRODUCED,
            detail=(f"no produced percept matches '{actuator}'"
                    + (f" on {image}" if image else "")), **base)
    if len(matched) > 1:
        # Refuse to pick. An article that drew the wrong field beside a true sentence would be
        # believed by every reader and contradicted by nothing in the document.
        #
        # The two ways to get here are NOT the same failure and must not read as though they
        # were. Down the weak-key path the step is genuinely unknown. Down the exact path the
        # step is known precisely and produced several drawable percepts — a real modelling
        # question about which one the sentence meant, not a provenance gap. Reporting the old
        # reason for the new case would send a reader to fix something already fixed.
        if by_step:
            why = (f"; none was chosen because step '{step_id}' produced {len(matched)} "
                   "drawable percepts and the citation does not say which")
        else:
            why = "; none was chosen because a suggestion does not record its step"
        return ResolvedCitation(
            status=AMBIGUOUS,
            detail=(f"{len(matched)} produced percepts match '{actuator}'"
                    + (f" on {image}" if image else "") + why),
            candidates=tuple(str(s.get("source_ref") or "") for s in matched), **base)

    found = matched[0]
    geometry = found.get("geometry") if isinstance(found.get("geometry"), dict) else None
    return ResolvedCitation(
        status=RESOLVED, geometry=geometry,
        geometry_kind=str((geometry or {}).get("kind") or ""),
        label=str(found.get("label") or found.get("role") or ""),
        source_ref=str(found.get("source_ref") or ""), **base)


# ── the whole article ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResolvedArticle:
    """M3's draft with every citation joined to live geometry. What M4's renderer consumes.

    The draft is carried VERBATIM alongside the resolution rather than rewritten into it: the
    prose, the caveats, the relevance flags and the qualifications are M3's and must reach the
    reader exactly as M3 wrote them. This adds a layer; it does not edit one.
    """
    draft: Dict[str, Any]
    citations: Tuple[ResolvedCitation, ...] = ()
    version: int = RESOLVER_VERSION

    @property
    def by_step_id(self) -> Dict[str, ResolvedCitation]:
        return {c.step_id: c for c in self.citations}

    @property
    def drawable(self) -> Tuple[ResolvedCitation, ...]:
        return tuple(c for c in self.citations if c.drawable)

    @property
    def unresolved(self) -> Tuple[ResolvedCitation, ...]:
        return tuple(c for c in self.citations if c.status != RESOLVED)

    def images(self) -> Tuple[str, ...]:
        """Every source image the article draws on, in first-cited order."""
        return tuple(dict.fromkeys(c.image for c in self.citations if c.image))

    def to_dict(self) -> Dict[str, Any]:
        resolved = {c.step_id: c.to_dict() for c in self.citations}
        return {
            "version": self.version,
            "draft": self.draft,
            # Keyed by step_id: the renderer walks the draft's sections and looks each citation up
            # here, so the two structures cannot drift out of order.
            "resolved": resolved,
            "images": list(self.images()),
            "counts": {
                "citations": len(self.citations),
                "drawable": len(self.drawable),
                "unresolved": len(self.unresolved),
            },
        }


def _all_citations(draft: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every citation in the draft, sections then counter-reading, de-duplicated by step_id."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for section in (draft.get("sections") or []):
        for citation in (section.get("citations") or []):
            sid = str(citation.get("step_id") or "")
            if sid in seen:
                continue
            seen.add(sid)
            out.append(citation)
    counter = draft.get("counter_reading") or {}
    for citation in (counter.get("citations") or []):
        sid = str(citation.get("step_id") or "")
        if sid in seen:
            continue
        seen.add(sid)
        out.append(citation)
    return out


def resolve_article(draft: Dict[str, Any], suggestions: Sequence[Dict[str, Any]],
                    memory: WorkingMemory) -> ResolvedArticle:
    """An `ArticleDraft.to_dict()` + the run's quarantined suggestions → a renderable article.

    READ-ONLY. Nothing here writes a post, accepts a mark, or edits the draft. The article stays
    exactly what M3 made it: a quarantined proposal.
    """
    citations = tuple(resolve_citation(c, suggestions, memory) for c in _all_citations(draft))
    return ResolvedArticle(draft=draft, citations=citations)
