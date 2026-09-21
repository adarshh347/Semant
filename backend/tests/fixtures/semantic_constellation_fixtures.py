"""Synthetic stored dissolution outputs. No private interpretation or image is included."""
from backend.schemas.inquiry_session import SemanticInquirySession
from backend.schemas.semantic_constellation import ThoughtInput
from backend.schemas.semantic_compilation import (
    SemanticInquiryGraph, GraphProvenance, SemanticAtom, ClaimNode, ClaimEdge,
    SourcePointer, CoverageDisposition,
)
from backend.services.semantic_compilation import ledger, ids

STAMP = "2026-09-19T00:00:00+00:00"
CASES = {
    "flower": (
        "Separate marks have broken boundaries. Together they suggest a flower. "
        "The relation between separation and recognition remains uncertain.",
        "How can separate marks suggest a flower while their boundaries remain broken?",
    ),
    "branching": (
        "Two branches share a junction. The routes can be grouped by destination. "
        "A shared junction does not settle which routes belong together.",
        "Should these branching routes be grouped by junction or destination?",
    ),
}


def session_for(name="flower", *, compiled=True):
    prompt, _ = CASES[name]
    inquiry = "inq_synthetic_" + name
    session = SemanticInquirySession(session_id="inqs_synthetic_" + name, inquiry_id=inquiry,
                                     prompt=prompt)
    if not compiled:
        return session
    units, _ = ledger.build(prompt, None, inquiry_id=inquiry)
    atoms, claims, coverage = [], [], []
    # The final relational question is deliberately absent from claims. Its source survives.
    for i, unit in enumerate(units):
        atom = SemanticAtom(atom_id=ids.atom_id(inquiry, "interpretation", unit.exact_quote,
                                               [unit.source_unit_id]),
                            text=unit.exact_quote, unit_kind="interpretation", author="user",
                            source_unit_ids=[unit.source_unit_id], quotes=[unit.exact_quote])
        atoms.append(atom)
        coverage.append(CoverageDisposition(coverage_id=ids.coverage_id(inquiry, unit.source_unit_id),
            source_unit_id=unit.source_unit_id, disposition="represented_by", refs=[atom.atom_id]))
        if i < 2:
            claims.append(ClaimNode(claim_id=ids.claim_id(inquiry, "interpretation", atom.text),
                text=atom.text, claim_kind="interpretation", atom_refs=[atom.atom_id],
                sources=[SourcePointer(source_type="prompt", source_id="prompt",
                                       text=unit.exact_quote, span=unit.span)]))
    if name == "branching":
        claims.append(ClaimNode(claim_id=ids.claim_id(inquiry, "interpretation", "Grouping is ambiguous"),
            text="Grouping is ambiguous", claim_kind="interpretation",
            inferred_from=[c.claim_id for c in claims],
            sources=[SourcePointer(source_type="compiler_inference", source_id="synthetic-architect",
                                   text="synthetic inference")]))
    graph = SemanticInquiryGraph(graph_id=ids.graph_id(inquiry, prompt), inquiry_id=inquiry,
        prompt=prompt, source_units=units, semantic_atoms=atoms, coverage=coverage,
        claims=claims, claim_edges=[ClaimEdge(edge_id=ids.edge_id(inquiry, "complicates",
            claims[1].claim_id, claims[0].claim_id), kind="complicates",
            from_claim=claims[1].claim_id, to_claim=claims[0].claim_id,
            why="synthetic frozen relation; no claim of semantic preservation")],
        provenance=GraphProvenance(producer="synthetic-constellation-fixture", compiler_kind="fixture",
                                   prompt_sha256="synthetic", compiled_at=STAMP))
    return session.model_copy(update={"graph": graph.model_dump(mode="json", by_alias=True)})


def thought_for(session):
    return ThoughtInput(organising_question=CASES[session.session_id.rsplit("_", 1)[-1]][1],
        anchors=[{"origin": "user_prompt", "source_id": "prompt", "span": [0, len(session.prompt)],
                  "exact_text": session.prompt}], authorship={"kind": "human", "actor": "fixture-author"},
        confirmed_by="fixture-author", alternatives=[
            {"text": "The elements sustain a joint reading", "authorship": {
                "kind": "human", "actor": "fixture-author"}},
            {"text": "The grouping remains ambiguous", "authorship": {
                "kind": "human", "actor": "fixture-author"}}])
