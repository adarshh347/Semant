import React from 'react';
import {
    BasisChip, EpistemicChip, LifecycleChip, ScopeChip, VerdictChip, EmptyState, Refusal,
} from './Chips';
import { artifactSummary, ceilingNote, duration, num, orderedMeasurements } from '../display';
import { missingConsumedFields } from '../contract/perceptionLabContract';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the six blocks, kept six.
 *
 * The contract's separation laws are not a storage detail; they are the only thing standing
 * between a measurement and the reading a person will attach to it. So this inspector renders
 * them as six labelled sections in a fixed order, each with the sentence that says what KIND of
 * fact it holds:
 *
 *     identity        what this is and what it was made from — session-local unless it says otherwise
 *     measurement     the numbers, with the basis they were taken on and the ceiling that basis has
 *     projection      how it is being DRAWN. Never geometry: `projection.hints` is clamped
 *     interpretation  the reading. Its OWN epistemic status, which is not the measurement's
 *     lifecycle       a curation state. Not a judgement, and it does not move when one is recorded
 *     provenance      who produced it, with what, when, and at what cost
 *
 * A human verdict is rendered SEPARATELY and last, and is labelled as a separate record, because
 * the contract keeps it in a separate record. A `reviews` field inside this panel is exactly how
 * `correct` starts being read as a property of the measurement.
 *
 * `missingConsumedFields` runs on every artifact. If Lane F's backend drops a path the surface
 * depends on, this says which one rather than rendering a blank where a number should be.
 */
export default function ArtifactInspector({ artifact, reviews = [], onFocusInstance = null,
    focusedInstanceId = null, children = null }) {
    if (!artifact) {
        return (
            <section className="pl-panel" aria-label="Inspector">
                <div className="pl-panel-head"><h2 className="pl-panel-title">Inspector</h2></div>
                <EmptyState title="Nothing is active"
                    hint="Choose an artifact in the ledger. This panel keeps identity,
                        measurement, projection, interpretation, lifecycle and provenance apart,
                        because the contract does." />
            </section>
        );
    }

    const { identity, measurement, projection, interpretation, lifecycle, provenance } = artifact;
    const missing = missingConsumedFields('PerceptualArtifact', artifact);
    const payload = measurement.payload;
    const isRefusal = payload?.variant === 'refusal';

    return (
        <section className="pl-panel" aria-label="Inspector"
            data-artifact-id={identity.artifact_id}>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Inspector</h2>
                <span className="pl-chiprow">
                    <ScopeChip scope={identity.identity_scope} />
                    <span className="pl-chip" data-artifact-kind={identity.artifact_kind}>
                        {identity.artifact_kind}
                    </span>
                </span>
            </div>
            <p className="pl-panel-sub" data-artifact-summary>{artifactSummary(artifact)}</p>

            {missing.length ? (
                <p className="pl-error" role="alert" data-missing-fields={missing.join(',')}>
                    This record is missing fields this surface reads: {missing.join(', ')}. What is
                    shown below is incomplete, and the gaps are not zeroes.
                </p>
            ) : null}

            {/* ── 1. identity ─────────────────────────────────────────────── */}
            <section className="pl-field" data-block="identity" aria-label="Identity">
                <span className="pl-label">Identity</span>
                <dl className="pl-kv">
                    <dt>artifact</dt><dd><code>{identity.artifact_id}</code></dd>
                    <dt>scope</dt>
                    <dd data-identity-scope={identity.identity_scope}>
                        {identity.identity_scope === 'session'
                            ? 'session-local. This id exists inside this laboratory and Semant has '
                                + 'never heard of it.'
                            : 'canonical — an identity Semant holds.'}
                    </dd>
                    <dt>organ</dt><dd>{identity.organ_family} · <code>{identity.operation}</code></dd>
                    <dt>from run</dt><dd><code>{identity.run_id}</code> step <code>{identity.step_id}</code></dd>
                    <dt>inputs</dt>
                    <dd data-input-count={identity.input_refs.length}>
                        {identity.input_refs.length
                            ? identity.input_refs.map((r) => (
                                <span key={`${r.role}-${r.artifact_id}-${r.instance_id || ''}`}
                                    className="pl-row-name" data-input-ref={r.artifact_id}
                                    data-input-instance={r.instance_id || ''}>
                                    {r.role}={r.artifact_id}
                                    {r.instance_id ? `#${r.instance_id}` : ''}{' '}
                                </span>
                            ))
                            : 'none — this was taken from the image itself'}
                    </dd>
                    <dt>cites</dt>
                    <dd data-identity-refs={identity.identity_refs.length}>
                        {identity.identity_refs.length
                            ? identity.identity_refs.map((r, i) => (
                                <span key={i} className="pl-row-name" data-cites-scope={r.scope}>
                                    {r.scope}:{r.region_id || r.artifact_id}
                                    {r.geometry_rev !== null ? ` @rev${r.geometry_rev}` : ''}{' '}
                                </span>
                            ))
                            : 'nothing canonical'}
                    </dd>
                </dl>
            </section>

            {/* ── 2. measurement ──────────────────────────────────────────── */}
            <section className="pl-field" data-block="measurement" aria-label="Measurement">
                <span className="pl-label">Measurement</span>
                <span className="pl-chiprow">
                    <EpistemicChip status={measurement.epistemic_status} />
                    <BasisChip basis={measurement.epistemic_basis} />
                </span>
                <dl className="pl-kv">
                    <dt>variant</dt><dd><code>{measurement.payload_variant}</code></dd>
                    <dt>coordinates</dt><dd>{measurement.coordinate_system}</dd>
                    <dt>basis</dt>
                    <dd data-basis-detail>{measurement.basis_detail}</dd>
                    <dt>ceiling</dt>
                    <dd data-ceiling>
                        {ceilingNote(measurement.epistemic_basis)}
                        {measurement.epistemic_basis === 'box'
                            ? ' — however confident the number is.' : ''}
                    </dd>
                    {measurement.data_ref ? (
                        <>
                            <dt>held at</dt>
                            <dd data-data-ref={measurement.data_ref}>
                                <code>{measurement.data_ref}</code> — the values are behind this
                                reference and are not in the record.
                            </dd>
                        </>
                    ) : null}
                </dl>
                {isRefusal ? <Refusal refusal={payload.refusal} /> : null}
                <PayloadReading payload={payload} onFocusInstance={onFocusInstance}
                    focusedInstanceId={focusedInstanceId} />
            </section>

            {/* ── 3. projection ───────────────────────────────────────────── */}
            <section className="pl-field" data-block="projection" aria-label="Projection">
                <span className="pl-label">Projection</span>
                <dl className="pl-kv">
                    <dt>kind</dt>
                    <dd data-projection-kind={projection.projection_kind}>
                        {projection.projection_kind}
                    </dd>
                    <dt>hints</dt>
                    <dd data-hint-keys={Object.keys(projection.hints || {}).join(',')}>
                        {Object.keys(projection.hints || {}).length
                            ? Object.entries(projection.hints)
                                .map(([k, v]) => `${k}: ${v}`).join(' · ')
                            : 'none'}
                    </dd>
                </dl>
                <p className="pl-panel-sub">
                    How this is drawn, and nothing about where it is. The hint keys are a closed
                    set, so no geometry can arrive through this block dressed as presentation.
                </p>
            </section>

            {/* ── 4. interpretation ───────────────────────────────────────── */}
            <section className="pl-field" data-block="interpretation" aria-label="Interpretation">
                <span className="pl-label">Interpretation</span>
                <span className="pl-chiprow">
                    <EpistemicChip status={interpretation.epistemic_status} />
                </span>
                <dl className="pl-kv">
                    <dt>label</dt>
                    <dd data-label-source={interpretation.label_source}>
                        {interpretation.label === null
                            ? 'no name. Nothing has been read into this yet, and an absent name is '
                                + 'not an unknown object.'
                            : `“${interpretation.label}” · from ${interpretation.label_source}`}
                    </dd>
                    {interpretation.notes ? (
                        <><dt>notes</dt><dd>{interpretation.notes}</dd></>
                    ) : null}
                </dl>
                <p className="pl-panel-sub">
                    A reading of the measurement above, carrying its OWN status. A measured mask
                    with an interpretive name is the ordinary case, not a contradiction.
                </p>
            </section>

            {/* ── 5. lifecycle ────────────────────────────────────────────── */}
            <section className="pl-field" data-block="lifecycle" aria-label="Lifecycle">
                <span className="pl-label">Lifecycle</span>
                <span className="pl-chiprow">
                    <LifecycleChip status={lifecycle.status} />
                    <span className="pl-chip">{lifecycle.changed_by}</span>
                </span>
                <p className="pl-panel-sub" data-lifecycle-note>
                    A curation state in this laboratory’s ledger. It is not a judgement about the
                    measurement and it does not move when one is recorded. Nothing here writes into
                    Semant.
                </p>
            </section>

            {/* ── 6. provenance ───────────────────────────────────────────── */}
            <section className="pl-field" data-block="provenance" aria-label="Provenance">
                <span className="pl-label">Provenance</span>
                <dl className="pl-kv">
                    <dt>produced by</dt>
                    <dd data-producer-kind={provenance.producer_kind}>
                        {provenance.producer_kind} · {provenance.producer}
                    </dd>
                    <dt>adapter</dt>
                    <dd data-provenance-adapter={provenance.adapter || 'none'}>
                        {provenance.adapter || 'none — nothing was dispatched'}
                        {provenance.model ? ` · ${provenance.model}` : ''}
                        {provenance.revision ? ` @ ${provenance.revision}` : ''}
                    </dd>
                    <dt>image</dt>
                    <dd data-source-digest>{provenance.source_image_digest}</dd>
                    <dt>took</dt><dd>{duration(provenance.duration_ms)}</dd>
                    {provenance.device ? (
                        <><dt>device</dt><dd>{provenance.device}</dd></>
                    ) : null}
                    {provenance.peak_memory_mb !== null
                        && provenance.peak_memory_mb !== undefined ? (
                            <><dt>peak memory</dt><dd>{num(provenance.peak_memory_mb)} MB</dd></>
                        ) : null}
                </dl>
            </section>

            {children}

            {/* ── a separate record, said so ──────────────────────────────── */}
            <section className="pl-field" data-block="reviews" aria-label="Human verdicts">
                <span className="pl-label">Human verdicts — a separate record</span>
                {reviews.length === 0 ? (
                    <p className="pl-panel-sub" data-no-reviews>
                        Nobody has judged this. That is not the same as unclear, which is a verdict
                        somebody recorded.
                    </p>
                ) : (
                    <ul className="pl-list">
                        {reviews.map((r) => (
                            <li key={r.review_id} className="pl-turn" data-review={r.review_id}>
                                <span className="pl-chiprow">
                                    <VerdictChip verdict={r.verdict} />
                                    <span className="pl-chip">{r.reviewer}</span>
                                </span>
                                {r.notes ? <span className="pl-turn-text">{r.notes}</span> : null}
                                <span className="pl-turn-meta">{r.reviewed_at}</span>
                            </li>
                        ))}
                    </ul>
                )}
                <p className="pl-axisnote">
                    Kept in its own record, keyed by artifact id. The measurement above is
                    unchanged by anything in this list, and so is the lifecycle.
                </p>
            </section>
        </section>
    );
}

/**
 * The payload, read as what it is.
 *
 * Extent instances are individually addressable, because "select one extent inside a multi-extent
 * artifact" is the ordinary case and a set that could only be taken whole would force a person to
 * measure five things to ask about one.
 */
function PayloadReading({ payload, onFocusInstance, focusedInstanceId }) {
    if (!payload) return null;

    if (payload.variant === 'extent_set') {
        return (
            <div data-payload="extent_set">
                <dl className="pl-kv">
                    <dt>searched</dt><dd data-searched>“{payload.searched}”</dd>
                    <dt>found</dt><dd data-instance-count>{payload.instances.length}</dd>
                    {payload.dropped_below_min_area !== null ? (
                        <>
                            <dt>dropped</dt>
                            <dd data-dropped-small={payload.dropped_below_min_area}>
                                {payload.dropped_below_min_area} below the minimum area — found,
                                and set aside by a bound rather than absent from the image
                            </dd>
                        </>
                    ) : null}
                    {payload.duplicates?.length ? (
                        <>
                            <dt>duplicates</dt>
                            <dd data-duplicates={payload.duplicates.length}>
                                {payload.duplicates.map((d, i) => (
                                    <span key={i}>
                                        {d.a}≈{d.b} (IoU {num(d.iou)}){' '}
                                    </span>
                                ))}
                            </dd>
                        </>
                    ) : null}
                </dl>
                {payload.instances.length === 0 ? (
                    <p className="pl-panel-sub" data-empty-extent>
                        The organ looked and found nothing of that kind. This is a measurement:
                        it is not the same as not having looked.
                    </p>
                ) : (
                    <ul className="pl-list" data-instances>
                        {payload.instances.map((inst) => (
                            <li key={inst.instance_id}>
                                <button type="button" className="pl-row"
                                    data-instance={inst.instance_id}
                                    aria-pressed={focusedInstanceId === inst.instance_id}
                                    disabled={!onFocusInstance}
                                    onClick={() => onFocusInstance?.(inst.instance_id)}>
                                    <span className="pl-row-name">{inst.instance_id}</span>
                                    <span className="pl-row-meta" data-instance-naming>
                                        {inst.naming
                                            ? `“${inst.naming.text}” · ${inst.naming.epistemic_status}`
                                            : 'unnamed — the name is withheld, not unknown'}
                                    </span>
                                    <span className="pl-row-meta">
                                        {inst.mask_rle ? 'mask' : 'box only'} ·{' '}
                                        area {num(inst.area)}
                                        {inst.geometry_rev !== null
                                            ? ` · rev ${inst.geometry_rev}` : ''}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        );
    }

    if (payload.variant === 'topology_relation_set') {
        return (
            <div data-payload="topology_relation_set">
                <dl className="pl-kv">
                    <dt>pairs examined</dt>
                    <dd data-pairs-examined={payload.pairs_examined}>{payload.pairs_examined}</dd>
                    <dt>relations held</dt>
                    <dd data-relation-count={payload.relations.length}>
                        {payload.relations.length}
                    </dd>
                    {payload.bounded_to !== null ? (
                        <>
                            <dt>bounded to</dt>
                            <dd data-bounded-to={payload.bounded_to}>
                                {payload.bounded_to} — a bound was applied, and it is on the record
                            </dd>
                        </>
                    ) : null}
                </dl>
                {payload.relations.length === 0 ? (
                    <p className="pl-panel-sub" data-empty-relations>
                        {payload.pairs_examined} pairs were examined and none held that relation.
                        Pairs examined with no relation is a finding; zero pairs examined would
                        have been an absence of measurement.
                    </p>
                ) : (
                    <ul className="pl-list" data-relations>
                        {payload.relations.map((rel) => (
                            <li key={rel.relation_id} className="pl-step"
                                data-relation={rel.relation_id} data-relation-kind={rel.kind}>
                                <span className="pl-step-op" data-relation-direction={
                                    rel.directed ? 'directed' : 'symmetric'}>
                                    {rel.source.instance_id || rel.source.artifact_id}
                                    {rel.directed ? ' → ' : ' — '}
                                    {rel.target.instance_id || rel.target.artifact_id}
                                    {' '}({rel.kind})
                                </span>
                                <span className="pl-chiprow">
                                    <BasisChip basis={rel.basis} />
                                    <EpistemicChip status={rel.epistemic_status} />
                                    {rel.stale ? (
                                        <span className="pl-stale" data-stale>
                                            stale — an endpoint has moved since this was measured
                                        </span>
                                    ) : null}
                                </span>
                                <span className="pl-step-why">
                                    {orderedMeasurements(rel.measurements)
                                        .map((m) => `${m.key} ${num(m.value)}`).join(' · ')
                                        || 'no scalar measurement'}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        );
    }

    if (payload.variant === 'negative_space_field') {
        return (
            <div data-payload="negative_space_field">
                <dl className="pl-kv">
                    <dt>figures</dt>
                    <dd data-figures={payload.figure_instance_ids.join(',')}>
                        {payload.figure_instance_ids.join(', ')}
                    </dd>
                    <dt>field</dt>
                    <dd data-field-shape={payload.field_shape.join('×')}>
                        {payload.field_shape.join(' × ')} · capped at{' '}
                        {num(payload.max_distance_used)}
                    </dd>
                    <dt>values</dt>
                    <dd data-field-ref={payload.field_ref || 'none'}>
                        {payload.field_ref
                            ? <>behind <code>{payload.field_ref}</code> — the numbers are not in
                                this record and this laboratory will not invent them</>
                            : 'not carried'}
                    </dd>
                </dl>
                {Object.keys(payload.statistics || {}).length ? (
                    <dl className="pl-kv" data-field-statistics>
                        {orderedMeasurements(payload.statistics).map((m) => (
                            <React.Fragment key={m.key}>
                                <dt>{m.key}</dt><dd>{num(m.value)}</dd>
                            </React.Fragment>
                        ))}
                    </dl>
                ) : null}
            </div>
        );
    }

    return null;
}
