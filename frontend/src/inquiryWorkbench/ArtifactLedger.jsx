import React, { useState } from 'react';
import {
    DISPOSITION_COPY, VERDICT_COPY, STATUS_COPY, uncoveredSourceUnits,
    PASS_LABEL, PASS_OUTCOME_COPY, WAIT_SOURCE_COPY, formatDuration,
} from './inquiryContract';
import { ImageRef, ImageRefList } from './ImageInspector.jsx';

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
    parents = [], imageRefs = [], raw = null }) {
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
                    {/* SEPARATE FROM `from`, and openable. An image reference is the one source
                        pointer on this panel that resolves to something a person can look at, and
                        it used to print in the same comma list as `prompt#0:62` — where it read as
                        one more opaque token. */}
                    {imageRefs.length ? (
                        <div>
                            <dt>rests on</dt>
                            <dd><ImageRefList refs={imageRefs} /></dd>
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

/**
 * What one mind of the council did — HARNESS-003D.
 *
 * `provenance.compiler` is null on a v2 graph and that is deliberate: naming one of three minds as
 * the author of the whole thing would be a lie, and the pass list IS the receipt. So this row is
 * the only place a reader can find out WHICH mind came up short, which is the question 002R's
 * one-call compiler made unanswerable.
 *
 * Three numbers that a careless row would merge:
 *
 *   calls        how many times this pass ASKED a model
 *   sends        how many times bytes went on the wire — identical re-sends after a capacity refusal
 *   waited       time spent queueing for the account's allowance, not for the model
 *
 * A run whose elapsed time is mostly `waited` is not slow. It is a run inside a smaller allowance
 * than the work needs, and the repairs are opposite.
 */
export function PassRow({ pass }) {
    const name = pass.pass_name.known ? pass.pass_name.value : 'unknown';
    const outcome = pass.outcome.known ? pass.outcome.value : 'unknown';
    return (
        <li
            className={`iw-pass${pass.underperformed ? ' is-underperforming' : ''}`}
            data-pass={name}
            data-pass-outcome={pass.outcome.value}
        >
            <span className="iw-led-item-head">
                <span className="iw-pass-name">
                    {pass.pass_name.known
                        ? PASS_LABEL[name]
                        : <>a pass this client does not recognise
                            (<span className="iw-badge-raw">{pass.pass_name.value}</span>)</>}
                </span>
                <span
                    className={`iw-pass-outcome iw-pass-outcome--${outcome}`}
                    data-outcome={pass.outcome.value}
                >
                    {pass.outcome.known
                        ? outcome
                        : <>unknown: <span className="iw-badge-raw">{pass.outcome.value}</span></>}
                </span>
            </span>

            {pass.outcome.known && PASS_OUTCOME_COPY[outcome] ? (
                <p className="iw-quiet">{PASS_OUTCOME_COPY[outcome]}</p>
            ) : null}
            {pass.detail ? <p className="iw-led-text">{pass.detail}</p> : null}

            <ul className="iw-pass-facts">
                {pass.model ? <li data-fact="model"><code>{pass.model}</code></li> : null}
                {/* A deterministic pass genuinely made no call, and `0 calls` is the right thing to
                    print for it. A pass that reported no count at all prints nothing — an
                    unreported count is not zero, which is the same law `counts_line` follows. */}
                {pass.call_count !== null ? (
                    <li data-fact="calls">{pass.call_count} call{pass.call_count === 1 ? '' : 's'}</li>
                ) : null}
                {/* SHOWN ONLY WHERE IT DIFFERS. Sends equal to calls is the ordinary case and
                    printing it everywhere would bury the one case that matters. */}
                {pass.transport_attempts !== null && pass.transport_attempts !== pass.call_count ? (
                    <li data-fact="sends">
                        {pass.transport_attempts} send{pass.transport_attempts === 1 ? '' : 's'}
                        {' '}— identical bytes, re-sent after a capacity refusal
                    </li>
                ) : null}
                <li data-fact="duration">{formatDuration(pass.duration_ms)} in the model</li>
                {/* NULL IS AN EM DASH AND NOT `0 ms`. `waited_ms` is only present where something
                    waited, so a row printing zero would report an unpaced run as a paced one that
                    never hit the limit. */}
                {pass.waited_ms !== null ? (
                    <li data-fact="waited" className="iw-pass-waited">
                        {formatDuration(pass.waited_ms)} waiting for provider capacity
                    </li>
                ) : null}
                {pass.finish_reasons.length ? (
                    <li data-fact="finish">
                        finish {pass.finish_reasons.join(', ')}
                    </li>
                ) : null}
            </ul>

            {/* HOW THE PASS WAS CUT UP, and what that cost. HARNESS-003E.

                One request over every atom could not be sent — 9,827 tokens against an 8,000
                allowance — so the architect works in batches, and batching alone would make every
                relation crossing a boundary invisible. `pairs` is the number that says whether it
                looked: two batches nobody put in front of the model together is a relation nobody
                searched for. Unexamined pairs print in full WITH THEIR REASON, because a run the
                budget stopped and a comparison that found nothing are opposite facts. */}
            {pass.batch_plan ? (
                <div className="iw-pass-plan" data-batch-plan={pass.batch_plan.plan_id}>
                    <ul className="iw-pass-facts">
                        <li data-fact="batches">
                            {pass.batch_plan.batches} batch
                            {pass.batch_plan.batches === 1 ? '' : 'es'} over
                            {' '}{pass.batch_plan.total_items} {pass.batch_plan.unit || 'item'}
                            {pass.batch_plan.total_items === 1 ? '' : 's'}
                        </li>
                        {/* No pairs is not zero pairs compared: one batch held everything, so
                            there was nothing across. `pairs_complete` is null for exactly that. */}
                        {pass.batch_plan.pairs_total ? (
                            <li
                                data-fact="pairs"
                                className={pass.batch_plan.pairs_complete === false
                                    ? 'iw-pass-pairs--short' : ''}
                            >
                                {pass.batch_plan.pairs_examined} of {pass.batch_plan.pairs_total}
                                {' '}batch pair{pass.batch_plan.pairs_total === 1 ? '' : 's'}
                                {' '}compared across {pass.batch_plan.rounds.length} round
                                {pass.batch_plan.rounds.length === 1 ? '' : 's'}
                            </li>
                        ) : (
                            <li data-fact="pairs-none" className="iw-quiet">
                                one batch, so there was nothing across to compare
                            </li>
                        )}
                        {pass.batch_plan.unsendable_batches ? (
                            <li data-fact="unsendable">
                                {pass.batch_plan.unsendable_batches} batch
                                {pass.batch_plan.unsendable_batches === 1 ? '' : 'es'} too large to
                                {' '}send — refused before transport
                            </li>
                        ) : null}
                        {pass.batch_plan.duplicates_merged ? (
                            <li data-fact="duplicates">
                                {pass.batch_plan.duplicates_merged} duplicate claim
                                {pass.batch_plan.duplicates_merged === 1 ? '' : 's'} merged
                            </li>
                        ) : null}
                        {pass.batch_plan.largest_request_tokens !== null
                            && pass.batch_plan.allowance_tokens !== null ? (
                                <li data-fact="request-size" className="iw-quiet">
                                    largest request ~{pass.batch_plan.largest_request_tokens} of
                                    {' '}{pass.batch_plan.allowance_tokens} allowed
                                </li>
                            ) : null}
                    </ul>
                    {pass.batch_plan.unexamined_pairs.length ? (
                        <ul className="iw-pass-unexamined" data-unexamined-for={pass.pass_id}>
                            {pass.batch_plan.unexamined_pairs.map((p) => (
                                <li key={`${p.left}-${p.right}`} data-unexamined-pair="true">
                                    <b>never compared</b>
                                    {' — '}
                                    <code>{p.left}</code> and <code>{p.right}</code>
                                    {p.reason ? <span className="iw-quiet"> · {p.reason}</span>
                                        : null}
                                </li>
                            ))}
                        </ul>
                    ) : null}
                </div>
            ) : null}

            {pass.capacity_waits.length ? (
                <ol className="iw-pass-waits" data-waits-for={pass.pass_id}>
                    {pass.capacity_waits.map((w, i) => (
                        <li
                            key={`${pass.pass_id}-${i}`}
                            data-wait-source={w.source.value}
                            data-wait-taken={String(w.taken)}
                            className={w.taken === false ? 'iw-wait--stopped' : ''}
                        >
                            {w.taken === false
                                ? <b>the run stopped waiting</b>
                                : <>waited {w.seconds === null ? '—' : `${w.seconds}s`}</>}
                            {' — '}
                            {w.source.known
                                ? WAIT_SOURCE_COPY[w.source.value]
                                : <>an unrecognised reason
                                    (<span className="iw-badge-raw">{w.source.value}</span>)</>}
                            {w.detail ? <span className="iw-quiet"> · {w.detail}</span> : null}
                        </li>
                    ))}
                </ol>
            ) : null}

            <WhyHere
                id={pass.pass_id}
                producer={name}
                model={pass.model}
                sources={pass.inputs !== null ? [`${pass.inputs} input(s)`] : []}
                raw={pass.raw}
            />
        </li>
    );
}

export default function ArtifactLedger({ session }) {
    if (!session) return null;
    const g = session.graph;
    const uncovered = uncoveredSourceUnits(g);
    const cs = g.coverage_summary;

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
                                    <ImageRef refId={p.post_id} />
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
                                    imageRefs={b.image_refs}
                                    producer={g.reading.source || 'scene_theorist'}
                                    model={g.reading.model}
                                    status={{ value: g.reading.status, known: true }}
                                    raw={b.raw}
                                />
                            </li>
                        ))}
                    </ul>
                </Row>

                {/* THE COUNCIL, BEFORE ITS OUTPUT. Everything below this row was produced by one of
                    these passes, so a reader who finds a barren atom list needs this row first —
                    "the dissector was rate-limited out" and "the dissector found little" produce
                    the same empty list and send you to opposite repairs. */}
                <Row
                    id="passes"
                    label="Council passes"
                    count={g.passes.length}
                    schema="PassReceipt"
                    tone={g.passes.some((p) => p.underperformed) ? 'warn' : ''}
                    note={g.passes.some((p) => p.capacity_limited)
                        ? 'This run stopped waiting for provider capacity before every pass had '
                          + 'finished. What is below is what it got to, not what there was.'
                        : ''}
                >
                    <ol className="iw-led-items iw-passes">
                        {g.passes.map((p) => <PassRow key={p.pass_id} pass={p} />)}
                    </ol>
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
                                    sources={[u.source_ref].filter(Boolean)}
                                    imageRefs={u.image_refs}
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
                    {/* THE BACKEND'S OWN ARITHMETIC OVER ITS OWN LEDGER, not this client's. The
                        two agree today and the point of printing the backend's is that they must:
                        `lost` here and the rows below are computed on different sides of the wire,
                        so a divergence is visible rather than absorbed. */}
                    {cs.source_units !== null ? (
                        <p className="iw-quiet iw-coverage-summary" data-coverage-summary="true">
                            {cs.disposed} of {cs.source_units} source unit(s) disposed of
                            {' · '}{cs.represented} represented
                            {' · '}<b data-lost-count={cs.lost_count}>{cs.lost_count} lost</b>
                            {' · '}{cs.user_units} from you, {cs.reading_units} from the reading
                            {cs.complete === null ? null : (
                                <> · the ledger {cs.complete ? 'balances' : 'does NOT balance'}</>
                            )}
                        </p>
                    ) : null}
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
                                    imageRefs={a.image_scope}
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
                                    imageRefs={c.image_scope}
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
                    note={<>
                        What the judge concluded about each claim. <code>interpretive_only</code>
                        {' '}and <code>not_investigated</code> are different answers: one was
                        examined, the other was never asked.
                    </>}
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
