"""
ATLAS C5 — the writer node: an accepted plan becomes drafted prose, on the canvas, quarantined.

C4 left an accepted ArgumentPlan on the Atlas document — claims in an order, each bound to the
percepts that would carry it, `binding: planned` on every one of them. This turns that seed into
the prose of a perceptual article, and it does so by WRAPPING M3 and M4 rather than by composing
anything itself. There is no sentence-writing in this file, no citation logic, no epistemic
judgement: all of it belongs to `director/composition.py` and `director/article_resolver.py`, and
duplicating any of it here would create a second composer that could disagree with the first.

WHAT THIS MODULE ACTUALLY DOES, WHICH IS FOUR THINGS.

  1. REBUILDS THE ARGUMENT FROM THE STORED PLAN. The plan on the document is a VIEW — rows and
     strings, shaped for a canvas. M3 needs an `ArgumentPlan`. `argument_from_stored_plan` sends
     those rows back through the very functions C4's accept route used (`claims_from_payload` then
     `plan_argument`), so the argument M3 composes is re-judged against the corpus as it is NOW.
     A percept that has since stopped resolving comes back refused here, and the prose is never
     written for it. Reading the stored statuses instead would let an Atlas accepted last week
     compose an article about evidence that no longer binds.

  2. STATES WHY A PLAN CANNOT BE DRAFTED. `draft_blocker` answers, before anything runs, in the
     writer's words — no plan, no images, every claim refused. A blank draft surface with no reason
     on it is the failure mode this exists to prevent.

  3. HOLDS THE QUARANTINE. `stored_draft` is the shape the drafted article takes on the Atlas
     document, and it carries `committed: false` from M3's own draft, plus a `state` of
     `quarantined`. `assert_draft_is_quarantined` refuses to store anything that says otherwise.

  4. TURNS AN ACCEPTED DRAFT INTO MANUSCRIPT BLOCKS. `passages` is the only place prose crosses out
     of quarantine, and it is a pure function of the draft — so what Accept writes can be tested
     without a database, and can be read beside what the reader saw.

THE ORDER IS FORCED, AND IT IS THE POINT. M3 will not compose from a plan (`require_confirmation`);
it takes a chain provenance and re-judges through `confirm_against_chain` first. So the caller must
EXECUTE the accepted plan's percept chain and hand M3 what actually came back. `compose_from_chain`
is that call, kept here so the route stays a route. An article composed from the plan would describe
evidence that may never have been produced and would read exactly like one that was earned.

NON-SCOPE. Rendering is M4's `ArticleView` (the export artifact already exists; C5 does not draw a
second one). Persistence is `atlas_service.save_draft`. The HTTP shape is `routers/atlas.py`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import atlas_plan as P

# The quarantine vocabulary. `quarantined` is the only state a draft is ever STORED in; `accepted`
# and `dismissed` are transitions the document records after the prose has left for the manuscript
# or been dropped. Kept as strings in one place because the frontend branches on them.
DRAFT_QUARANTINED = "quarantined"
DRAFT_ACCEPTED = "accepted"
DRAFT_DISMISSED = "dismissed"

DRAFT_VERSION = 1

# Why a plan cannot be drafted from. Closed set — the panel renders each as a sentence.
BLOCK_NO_PLAN = "no_accepted_plan"
BLOCK_NO_IMAGES = "atlas_spans_no_images"
BLOCK_NO_CLAIMS = "the_accepted_plan_carries_no_claims"
BLOCK_ALL_REFUSED = "every_claim_in_the_plan_was_refused"

_BLOCK_TEXT = {
    BLOCK_NO_PLAN: ("No plan has been accepted on this Atlas. Plan an argument first — the writer "
                    "drafts from a plan that was judged, never from a thesis alone."),
    BLOCK_NO_IMAGES: ("This Atlas spans no images. There is nothing for a claim to rest on."),
    BLOCK_NO_CLAIMS: ("The accepted plan carries no claims. Plan again before drafting."),
    BLOCK_ALL_REFUSED: ("Every claim in the accepted plan was refused by the gate. Nothing here "
                        "can be carried, so nothing is written — read the refusals on the plan."),
}


def blocker_text(reason: str) -> str:
    """The writer-facing sentence for a blocker. Unknown reasons are returned as themselves rather
    than swallowed, because a blocker nobody can read is the same as no blocker at all."""
    return _BLOCK_TEXT.get(reason, reason)


def draft_blocker(doc: Mapping[str, Any]) -> Optional[str]:
    """Why this Atlas cannot be drafted from, or None. Checked BEFORE any producer runs.

    Ordered cheapest-first and most-fundamental-first: an Atlas with no images cannot be fixed by
    editing the plan, so it is reported ahead of the plan's own emptiness.
    """
    if not P.node_post_ids(doc):
        return BLOCK_NO_IMAGES
    plan = doc.get("plan")
    if not isinstance(plan, Mapping) or not plan:
        return BLOCK_NO_PLAN
    rows = [r for r in (plan.get("claims") or []) if isinstance(r, Mapping)]
    if not rows:
        return BLOCK_NO_CLAIMS
    # `struck` is C4's word for a claim the gate refused. A plan of nothing but struck claims is
    # not a draft waiting to happen; it is a refusal that has already been delivered.
    if all(bool(r.get("struck")) for r in rows):
        return BLOCK_ALL_REFUSED
    return None


def argument_from_stored_plan(doc: Mapping[str, Any], memory: Any) -> Tuple[Any, List[str]]:
    """The stored plan view → a re-bound `ArgumentPlan`, judged against the corpus as it is now.

    THIS DELIBERATELY RE-RUNS C4's ACCEPT PATH. `claims_from_payload` rebuilds the claims and clamps
    every param to the actuator's declared vocabulary; `plan_argument` binds them again through the
    unmodified gate. The stored statuses are READ BY NOBODY — an accepted `supported` is earned a
    third time here, at draft time, or it does not appear in the prose.
    """
    from .director.argument import plan_argument

    plan = doc.get("plan") or {}
    thesis = str(plan.get("thesis") or "").strip()
    claims, notes, _proposed = P.claims_from_payload(plan.get("claims"))
    if not claims:
        return None, list(notes) + ["the stored plan carried no claims that could be rebuilt"]
    argument = plan_argument(thesis, claims, memory, planner=P.PLANNER_ACCEPTED, notes=notes)
    return argument, list(notes)


def compose_from_chain(argument: Any, memory: Any, *, provenance: Any,
                       suggestions: Sequence[Mapping[str, Any]],
                       run_id: str = "", llm: Any = None) -> Dict[str, Any]:
    """M3 then M4, in the one order M3 permits. Returns the resolved-article payload.

    A thin seam and nothing more: `compose_article` is handed the provenance of a chain that really
    ran, and `resolve_article` joins each of its citations to the percept that was really produced.
    The draft is carried verbatim inside the result — M4's resolver adds a layer and never edits
    one, and neither does this.
    """
    from .director.article_resolver import resolve_article
    from .director.composition import LLM, compose_article

    draft = compose_article(argument, memory, provenance=provenance,
                            llm=llm if isinstance(llm, LLM) else LLM.from_service(),
                            run_id=run_id)
    payload = draft.to_dict()
    resolved = resolve_article(payload, list(suggestions), memory)
    return resolved.to_dict()


def stored_draft(article: Mapping[str, Any], *, thesis: str = "", run_id: str = "",
                 notes: Sequence[str] = (), now: str = "") -> Dict[str, Any]:
    """What a drafted article looks like on the Atlas document. QUARANTINED.

    The resolved article is stored WHOLE — draft, resolutions, counts — because that is exactly
    what M4's renderer consumes, and storing a reduction of it would mean the export re-derived
    something the reader had already been shown.
    """
    draft = dict(article.get("draft") or {})
    return {
        "version": DRAFT_VERSION,
        "state": DRAFT_QUARANTINED,
        # Mirrors M3's own field. Never computed here — if M3 ever said a draft was committed,
        # this would carry that and `assert_draft_is_quarantined` would refuse to store it.
        "committed": bool(draft.get("committed", False)),
        "thesis": thesis or str(draft.get("thesis") or ""),
        "run_id": run_id,
        "article": dict(article),
        "notes": list(notes),
        "drafted_at": now,
    }


def assert_draft_is_quarantined(draft: Optional[Mapping[str, Any]]) -> None:
    """Raise if a draft about to be stored claims to be anything but a proposal.

    The belt to `stored_draft`'s braces, in the spirit of `assert_plan_authors_no_evidence`: the
    invariant that prose stays a suggestion until a curator accepts it is worth a check that cannot
    be bypassed by a caller assembling the dict itself.
    """
    if not draft:
        return
    if draft.get("committed"):
        raise ValueError("a stored Atlas draft may never be `committed`; prose leaves quarantine "
                         "through the accept route, which writes the manuscript instead.")
    state = str(draft.get("state") or "")
    if state != DRAFT_QUARANTINED:
        raise ValueError(f"a stored Atlas draft must be '{DRAFT_QUARANTINED}', not '{state}'")
    inner = (draft.get("article") or {}).get("draft") or {}
    if inner.get("committed"):
        raise ValueError("M3's draft inside a stored Atlas draft says it is committed; refusing "
                         "to store prose that has stopped calling itself a proposal.")


# ── what Accept moves into the manuscript ────────────────────────────────────

def _paragraphs(text: Any) -> List[str]:
    return [p.strip() for p in str(text or "").split("\n\n") if p.strip()]


def passages(article: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The drafted article → the passages Accept writes into the manuscript.

    PURE, so what leaves quarantine can be read in a test beside what the reader saw on the canvas.

    WHAT CROSSES AND WHAT DOES NOT. Composed prose crosses: the opening, each section, the
    counter-reading when it is grounded. What M3 REFUSED does not become a paragraph — an
    uncomposed claim and a qualification are limits, and a limit pasted into a manuscript as body
    text becomes, on the next read, a finding. They travel as their own trailing passage, marked,
    so the writer keeps them without the manuscript asserting them.

    Every passage carries the step_ids it rests on. That is what makes an accepted paragraph still
    checkable after it has left the Atlas: the citation is not decoration on the canvas, it is the
    paragraph's provenance, and dropping it here would be the quiet moment where evidence-bound
    prose becomes ordinary prose.
    """
    draft = dict(article.get("draft") or {})
    out: List[Dict[str, Any]] = []

    thesis = str(draft.get("thesis") or "").strip()
    if thesis:
        out.append({"kind": "thesis", "heading": thesis,
                    "paragraphs": _paragraphs(draft.get("thesis_prose")),
                    "cites": [], "epistemic": str(draft.get("epistemic") or "")})

    for section in (draft.get("sections") or []):
        if not isinstance(section, Mapping):
            continue
        cites = [str(c.get("step_id") or "") for c in (section.get("citations") or [])
                 if isinstance(c, Mapping)]
        out.append({
            "kind": "section",
            "claim_id": str(section.get("claim_id") or ""),
            "heading": str(section.get("claim") or ""),
            "paragraphs": _paragraphs(section.get("prose")),
            "cites": [c for c in cites if c],
            "epistemic": str(section.get("epistemic") or ""),
            "function": str(section.get("function") or ""),
            # Carried, not dropped. A section that admitted something on the canvas admits it in
            # the manuscript too, or Accept was a way of laundering the admission.
            "caveats": [str(c) for c in (section.get("caveats") or [])],
            "qualified": bool(section.get("qualified")),
        })

    counter = draft.get("counter_reading")
    if isinstance(counter, Mapping) and counter.get("grounded"):
        cites = [str(c.get("step_id") or "") for c in (counter.get("citations") or [])
                 if isinstance(c, Mapping)]
        out.append({"kind": "counter", "heading": "The counter-reading",
                    "paragraphs": _paragraphs(counter.get("prose")),
                    "cites": [c for c in cites if c], "epistemic": ""})

    limits = limit_lines(article)
    if limits:
        out.append({"kind": "limits", "heading": "What this reading could not carry",
                    "paragraphs": limits, "cites": [], "epistemic": ""})
    return out


def limit_lines(article: Mapping[str, Any]) -> List[str]:
    """Every limit the article admits, as sentences: qualifications, uncomposed claims, and an
    ungrounded counter-reading. Stated as limits and never as findings."""
    draft = dict(article.get("draft") or {})
    lines: List[str] = []
    for q in (draft.get("qualifications") or []):
        if isinstance(q, Mapping) and q.get("prose"):
            lines.append(str(q["prose"]).strip())
    for u in (draft.get("uncomposed") or []):
        if not isinstance(u, Mapping):
            continue
        claim = str(u.get("claim") or "").strip()
        reason = str(u.get("reason") or "").replace("_", " ")
        if claim:
            lines.append(f"{claim} — not written: {reason}.")
    counter = draft.get("counter_reading")
    if isinstance(counter, Mapping) and not counter.get("grounded"):
        detail = str(counter.get("absence_detail") or "").strip()
        lines.append(detail or "No counter-reading could be grounded.")
    return lines


def passages_to_text_blocks(items: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Passages → the manuscript's `text_blocks` (the shape `manuscript_service` stores).

    HTML, because that is what the existing editor round-trips; the citation travels as a data
    attribute rather than as visible text, so an accepted paragraph reads as prose and still says
    what it rests on to anything that looks.
    """
    blocks: List[Dict[str, Any]] = []
    for item in items:
        heading = str(item.get("heading") or "").strip()
        if heading:
            blocks.append({"type": "heading", "content": _escape(heading)})
        cites = " ".join(str(c) for c in (item.get("cites") or []))
        attr = f' data-cites="{_escape(cites)}"' if cites else ""
        for para in (item.get("paragraphs") or []):
            blocks.append({"type": "paragraph", "content": f"<p{attr}>{_escape(para)}</p>"})
        for caveat in (item.get("caveats") or []):
            blocks.append({"type": "paragraph",
                           "content": f'<p data-caveat="true">{_escape(caveat)}</p>'})
    return blocks


def _escape(text: Any) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))
