import React, { useState } from 'react';
import {
    DISPOSITION_COPY, VERDICT_COPY, STATUS_COPY, uncoveredSourceUnits,
} from './inquiryContract';

/**
 * INQUIRY WORKBENCH — the whole chain, as objects rather than paragraphs.
 *
 * ```text
 * Prompt → Frame → Reading blocks → Source units → Atoms → Claims/edges
 *        → Observables → Decisions → Receipts → Verdicts → Synthesis
 * ```
 *
 * The 002R rehearsal's `disconnected_artifact` failure, addressed directly: the backend had
 * accumulated frame, posts, reading blocks, verdicts, gaps and provenance, and the client read
 * none of them. Every row below is a count the reader can open, and every object can say why it
 * is there.
 *
 * ## The links are the point, not the counts
 *
 * A row that said "4 claims" and stopped would be a different kind of concealment from the one it
 * replaced. So every object carries a **Why is this here?** panel with its source pointers, its
 * producer, its epistemic status, its parent refs and its raw record — and the raw record is the
 * escape hatch that keeps a field the backend added and this client has not learned visible
 * instead of dropped.
 *
 * ## Absence is rendered, not implied
 *
 * `grounds: 0`, `percepts: 0`, `evidence: 0`, `Atlas: 0` are printed as zeroes with a sentence
 * saying they are a property of the phase rather than a stage that has not finished. A blank space
 * where a count should be reads as "pending" to every reader, and this phase deliberately creates
 * none of those objects — a rehearsal that mistakes "never attempted" for "not yet arrived" will
 * ratify a phase on the strength of work nobody did.
 */

/** One expandable row. Count first, because "how much of this is there" is the first question. */
function Row({ id, label, count, schema, children, note = '', tone = '' }) {
    const [open, setOpen] = useState(false);
    const empty = count === 0;
    return (
        <li
            className={`iw-led-row${empty ? ' is-empty' : ''}${tone ? ` iw-led-row--${tone}` : ''}`}
            data-artifact={id}
            data-count={count}
        >
            <div className="iw-led-head">
                <span className="iw-led-count">{count}</span>
                <span className="iw-led-label">{label}</span>
                {schema ? <code className="iw-led-schema">{schema}</code> : null}
                {count > 0 ? (
                    <button
                        type="button"
                        className="iw-expand"
                        aria-expanded={open}
                        onClick={() => setOpen((v) => !v)}
                    >
                        {open ? 'Hide' : 'Open'}
                    </button>
                ) : null}
            </div>
            {note ? <p className="iw-quiet iw-led-note">{note}</p> : null}
            {open && count > 0 ? <div className="iw-led-body">{children}</div> : null}
        </li>
    );
}

/**
 * Why one object is here.
 *
 * Deliberately the same component for every artifact type. A per-type explanation panel would
 * drift, and the questions are the same whatever the object is: where did it come from, who made
 * it, how is it held, what does it hang off, and what does the record actually say.
 */
export function WhyHere({ id, sources = [], producer = '', model = '', status = null,
    parents = [], raw = null }) {
    const [open, setOpen] = useState(false);
    return (
        <div className="iw-why">
            <button
                type="button"
                className="iw-expand"
                aria-expanded={open}
                data-why-for={id}
                onClick={() => setOpen((v) => !v)}
            >
                {open ? 'Hide' : 'Why is this here?'}
            </button>
            {open ? (
                <dl className="iw-why-body" data-why-open={id}>
                    <div><dt>id</dt><dd><code>{id || '—'}</code></dd></div>
                    {sources.length ? (
                        <div>
                            <dt>from</dt>
                            <dd>{sources.map((s) => <code key={s}>{s}</code>)
                                .reduce((a, el, i) => (i ? [...a, ', ', el] : [el]), [])}</dd>
                        </div>
                    ) : null}
                    {parents.length ? (
                        <div>
                            <dt>hangs off</dt>
                            <dd>{parents.map((s) => <code key={s}>{s}</code>)
                                .reduce((a, el, i) => (i ? [...a, ', ', el] : [el]), [])}</dd>
                        </div>
                    ) : null}
                    <div><dt>produced by</dt><dd>{producer || 'not recorded'}</dd></div>
                    {model ? <div><dt>model</dt><dd><code>{model}</code></dd></div> : null}
                    {status && status.value ? (
                        <div>
                            <dt>held as</dt>
                            <dd>
                                {status.known
                                    ? <>{status.value} — {STATUS_COPY[status.value] || ''}</>
                                    : <>unknown: <span className="iw-badge-raw">{status.value}</span></>}
                            </dd>
                        </div>
                    ) : null}
                    {/* THE RAW RECORD. A field the backend added and this client has not learned
                        is visible here rather than dropped — which is the only way a reader can
                        tell "the surface does not show it" from "the backend did not send it". */}
                    {raw ? (
                        <div className="iw-why-raw">
                            <dt>raw record</dt>
                            <dd><pre>{JSON.stringify(raw, null, 2)}</pre></dd>
                        </div>
                    ) : null}
                </dl>
            ) : null}
        </div>
    );
}

const producerOf = (prov) => {
    const p = prov && typeof prov === 'object' ? prov : {};
    return String(p.role || p.producer || p.source || p.compiler || p.adapter || '');
};

const modelOf = (prov) => String((prov && typeof prov === 'object' && prov.model) || '');

export default function ArtifactLedger({ session }) {
    if (!session) return null;
    const g = session.graph;
    const uncovered = uncoveredSourceUnits(g);

    return (
        <section className="iw-panel iw-ledger" aria-label="Artifacts and provenance">
            <header>
                <h2 className="iw-h2">What this inquiry actually produced</h2>
                <p className="iw-quiet">
                    Every object the run made, in the order it made them. Open a row to read the
                    objects; open one object to see where it came from.
                </p>
            </header>

            <ol className="iw-led-list">
                <Row
                    id="prompt"
                    label="Prompt"
                    count={g.prompt ? 1 : 0}
                    schema="verbatim"
                    note="Byte-identical to what you typed. The source pointers index into it."
                >
                    <blockquote className="iw-led-prompt">{g.prompt}</blockquote>
                </Row>

                <Row id="posts" label="Images read" count={session.posts.length} schema="PostRef">
                    <ul className="iw-led-items">
                        {session.posts.map((p) => (
                            <li key={p.post_id} data-post-ref={p.post_id}>
                                <span className="iw-led-item-head">
                                    <code>{p.post_id}</code>
                                    {p.title ? <span>{p.title}</span> : null}
                                    {p.readable === false ? (
                                        <span className="iw-led-flag" data-unreadable="true">
                                            could not be read
                                        </span>
                                    ) : null}
                                </span>
                                {p.note ? <span className="iw-quiet">{p.note}</span> : null}
                                {/* The fingerprint, not a checkmark: Phase 1's claim is that no
                                    source post changed, and a comparison is evidence where a tick
                                    is an assurance. */}
                                {p.fingerprint ? (
                                    <span className="iw-quiet iw-led-fingerprint">
                                        fingerprint <code>{p.fingerprint.slice(0, 16)}…</code> —
                                        re-checked at every write
                                    </span>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="frame"
                    label="Frame"
                    count={session.frame ? 1 : 0}
                    schema="InquiryFrame"
                    note="What the framer read out of your words alone. It never sees pixels."
                >
                    <pre className="iw-led-raw">{JSON.stringify(session.frame, null, 2)}</pre>
                </Row>

                <Row
                    id="reading_blocks"
                    label="Reading blocks"
                    count={g.reading.blocks.length}
                    schema="ReadingBlock"
                    note="The theorist's output, split as it emitted it. These are what the
                          dissector consumes."
                >
                    <ul className="iw-led-items">
                        {g.reading.blocks.map((b) => (
                            <li key={b.block_id} data-block-id={b.block_id}>
                                <span className="iw-led-item-head">
                                    {b.kind ? <span className="iw-kind">{b.kind}</span> : null}
                                    <code>{b.block_id}</code>
                                </span>
                                <p className="iw-led-text">{b.text}</p>
                                <WhyHere
                                    id={b.block_id}
                                    sources={b.image_refs}
                                    producer={g.reading.source || 'scene_theorist'}
                                    model={g.reading.model}
                                    status={{ value: g.reading.status, known: true }}
                                    raw={b.raw}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="source_units"
                    label="Source units"
                    count={g.source_units.length}
                    schema="SourceUnit"
                    note="Every clause of your prompt and every block of the reading, each of which
                          must receive exactly one coverage disposition."
                >
                    <ul className="iw-led-items">
                        {g.source_units.map((u) => (
                            <li key={u.source_unit_id} data-source-unit={u.source_unit_id}>
                                <span className="iw-led-item-head">
                                    <span className="iw-kind">
                                        {u.source_type.known
                                            ? u.source_type.value.replace(/_/g, ' ')
                                            : `unknown: ${u.source_type.value}`}
                                    </span>
                                    <code>{u.source_unit_id}</code>
                                </span>
                                <q className="iw-led-quote">{u.exact_quote}</q>
                                <WhyHere
                                    id={u.source_unit_id}
                                    sources={[u.source_ref, ...u.image_refs].filter(Boolean)}
                                    producer="semantic_dissector"
                                    raw={u.raw}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="coverage"
                    label="Coverage dispositions"
                    count={g.coverage.length}
                    schema="CoverageDisposition"
                    tone={uncovered.length ? 'warn' : ''}
                    note={uncovered.length
                        ? `${uncovered.length} source unit${uncovered.length === 1 ? '' : 's'} `
                          + 'received no disposition at all. That is not a remainder — a remainder '
                          + 'is a decision — it is a unit the compiler lost.'
                        : ''}
                >
                    <ul className="iw-led-items">
                        {g.coverage.map((c) => (
                            <li key={c.source_unit_id} data-coverage-for={c.source_unit_id}>
                                <span className="iw-led-item-head">
                                    <code>{c.source_unit_id}</code>
                                    <span
                                        className={`iw-disposition iw-disposition--${c.disposition.known
                                            ? c.disposition.value : 'unknown'}`}
                                        data-disposition={c.disposition.value}
                                    >
                                        {c.disposition.known
                                            ? DISPOSITION_COPY[c.disposition.value]
                                            : `unknown: ${c.disposition.value}`}
                                    </span>
                                </span>
                                {c.reason ? <span className="iw-quiet">{c.reason}</span> : null}
                            </li>
                        ))}
                        {uncovered.map((u) => (
                            <li
                                key={u.source_unit_id}
                                className="iw-led-uncovered"
                                data-uncovered={u.source_unit_id}
                            >
                                <code>{u.source_unit_id}</code>
                                <span className="iw-led-flag">no disposition — lost</span>
                                <q className="iw-led-quote">{u.exact_quote}</q>
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="atoms"
                    label="Semantic atoms"
                    count={g.semantic_atoms.length}
                    schema="SemanticAtom"
                >
                    <ul className="iw-led-items">
                        {g.semantic_atoms.map((a) => (
                            <li key={a.atom_id} data-atom-id={a.atom_id}>
                                <span className="iw-led-item-head">
                                    <span className="iw-kind">
                                        {a.unit_kind.known
                                            ? a.unit_kind.value.replace(/_/g, ' ')
                                            : `unknown: ${a.unit_kind.value}`}
                                    </span>
                                    <code>{a.atom_id}</code>
                                    {a.author.value === 'user' ? (
                                        <span className="iw-author iw-author--user">
                                            your direction
                                        </span>
                                    ) : null}
                                </span>
                                <p className="iw-led-text">{a.text}</p>
                                <WhyHere
                                    id={a.atom_id}
                                    sources={a.source_unit_ids}
                                    producer={producerOf(a.provenance) || 'semantic_dissector'}
                                    model={modelOf(a.provenance)}
                                    status={a.epistemic_ceiling}
                                    raw={a.raw}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row id="claims" label="Claims" count={g.claims.length} schema="Claim">
                    <ul className="iw-led-items">
                        {g.claims.map((c) => (
                            <li key={c.claim_id} data-ledger-claim={c.claim_id}>
                                <span className="iw-led-item-head">
                                    <code>{c.claim_id}</code>
                                </span>
                                <p className="iw-led-text">{c.text}</p>
                                <WhyHere
                                    id={c.claim_id}
                                    sources={c.source_span
                                        ? [`${c.source_span.origin}: “${c.source_span.text}”`] : []}
                                    parents={c.image_scope}
                                    producer="semantic_compiler"
                                    status={c.status}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row id="claim_edges" label="Relations" count={g.claim_edges.length} schema="ClaimEdge">
                    <ul className="iw-led-items">
                        {g.claim_edges.map((e) => (
                            <li key={e.edge_id} data-ledger-edge={e.edge_id}>
                                <code>{e.from_claim}</code>
                                <span className="iw-relation">{e.relation}</span>
                                <code>{e.to_claim}</code>
                                {e.note ? <span className="iw-quiet">{e.note}</span> : null}
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="observables"
                    label="Observables"
                    count={g.observables.length}
                    schema="ObservableSpec"
                >
                    <ul className="iw-led-items">
                        {g.observables.map((o) => (
                            <li key={o.observable_id} data-ledger-observable={o.observable_id}>
                                <span className="iw-led-item-head">
                                    <code>{o.observable_id}</code>
                                    <span className="iw-kind">{o.observable_kind}</span>
                                    <span className="iw-quiet">
                                        {o.alternatives.length} alternative
                                        {o.alternatives.length === 1 ? '' : 's'}
                                    </span>
                                </span>
                                <p className="iw-led-text">{o.target}</p>
                                <WhyHere
                                    id={o.observable_id}
                                    parents={[o.claim_ref]}
                                    producer="epistemic_operationalizer"
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="decisions"
                    label="Decisions taken"
                    count={session.decision_records.length}
                    schema="DecisionRecord"
                >
                    <ul className="iw-led-items">
                        {session.decision_records.map((d) => (
                            <li key={d.record_id} data-ledger-decision={d.record_id}>
                                <span className="iw-led-item-head">
                                    <code>{d.decision_id}</code>
                                    <span className="iw-quiet">
                                        {d.decider.known ? d.decider.value : d.decider.value} chose
                                    </span>
                                </span>
                                <p className="iw-led-text">{d.selected_label || d.free_text}</p>
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="receipts"
                    label="Capability receipts"
                    count={session.capability_receipts.length}
                    schema="CapabilityReceipt"
                >
                    <ul className="iw-led-items">
                        {session.capability_receipts.map((r) => (
                            <li key={r.receipt_id} data-ledger-receipt={r.receipt_id}>
                                <span className="iw-led-item-head">
                                    <code>{r.receipt_id}</code>
                                    <span className="iw-kind">{r.capability}</span>
                                    {r.simulated ? (
                                        <span className="iw-simulated" data-simulated="true">
                                            SIMULATED — not evidence
                                        </span>
                                    ) : null}
                                </span>
                                <WhyHere
                                    id={r.receipt_id}
                                    parents={[r.request_ref]}
                                    producer={producerOf(r.provenance) || 'capability_broker'}
                                    raw={r.payload}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="verdicts"
                    label="Verdicts"
                    count={session.verdicts.length}
                    schema="ClaimVerdict"
                    note="What the judge concluded about each claim. `interpretive_only` and
                          `not_investigated` are different answers: one was examined, the other
                          was never asked."
                >
                    <ul className="iw-led-items">
                        {session.verdicts.map((v) => (
                            <li key={v.verdict_id} data-ledger-verdict={v.verdict_id}>
                                <span className="iw-led-item-head">
                                    <code>{v.claim_ref}</code>
                                    <span
                                        className={`iw-verdict iw-verdict--${v.outcome.known
                                            ? v.outcome.value : 'unknown'}`}
                                        data-verdict={v.outcome.value}
                                    >
                                        {v.outcome.known
                                            ? v.outcome.value.replace(/_/g, ' ')
                                            : `unknown: ${v.outcome.value}`}
                                    </span>
                                </span>
                                <p className="iw-led-text">
                                    {v.outcome.known ? VERDICT_COPY[v.outcome.value] : ''} {v.why}
                                </p>
                                <WhyHere
                                    id={v.verdict_id}
                                    parents={[v.claim_ref, ...v.receipt_refs]}
                                    sources={v.evidence_refs}
                                    producer="evidence_judge"
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                <Row
                    id="synthesis"
                    label="Answer sections"
                    count={session.synthesis ? session.synthesis.sections.length : 0}
                    schema="Synthesis"
                >
                    <ul className="iw-led-items">
                        {(session.synthesis?.sections || []).map((sec) => (
                            <li key={sec.section_id} data-ledger-section={sec.section_id}>
                                <span className="iw-led-item-head">
                                    <code>{sec.section_id}</code>
                                    <span>{sec.heading}</span>
                                </span>
                                <WhyHere
                                    id={sec.section_id}
                                    sources={sec.claim_refs}
                                    parents={sec.evidence_refs}
                                    producer="synthesis_composer"
                                    status={sec.status}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>
            </ol>

            <AbsenceLedger session={session} />
        </section>
    );
}

/**
 * The objects this phase does not create, printed as zeroes.
 *
 * A blank space where a count should be reads as "pending" to every reader. Phase 1 creates no
 * ground, no percept, no evidence and no Atlas edge BY DESIGN, and a rehearsal that mistakes
 * "never attempted" for "not yet arrived" will ratify a phase on the strength of work nobody did.
 * So the zeroes are printed, and the sentence beside them says which kind of zero they are — with
 * the tense depending on whether the run has finished, because "will not" and "did not" are
 * different promises.
 */
export function AbsenceLedger({ session }) {
    const ended = ['complete', 'exhausted', 'refused', 'error'].includes(session.state.value);
    const evidence = session.evidence.length;

    return (
        <div className="iw-absence" data-absence-ledger="true">
            <h3 className="iw-h3">What it did not create</h3>
            <ul className="iw-absence-list">
                <li data-absent="grounds"><b>grounds created: 0</b></li>
                <li data-absent="percepts"><b>percepts created: 0</b></li>
                <li data-absent="evidence"><b>evidence created: {evidence}</b></li>
                <li data-absent="atlas"><b>Atlas changes: 0</b></li>
                <li data-absent="marks"><b>marks committed: 0</b></li>
            </ul>
            <p className="iw-quiet iw-absence-note">
                {ended
                    ? 'This run is over and created none of these. '
                    : 'This phase creates none of these, and will not once the run finishes. '}
                A Phase-1 inquiry is interpretive throughout, and its one capability is a declared
                simulation. These are not stages still to come — nothing here is pending, and the
                source posts are unchanged.
            </p>
        </div>
    );
}
