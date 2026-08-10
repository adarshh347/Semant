import React, { useMemo } from 'react';
import { DerivedChip, EmptyState } from './Chips';
import { beforeAfter, decodeInstances, lineageOf, overlapMetrics } from '../extentView';
import { num } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the numbers beside the picture.
 *
 * Three readings that a stage alone cannot give, each of which is a way the Extent organ is
 * routinely believed without evidence:
 *
 *   NAMING       named, withheld and uncertain are three states and this panel keeps them three.
 *                An adapter that returns a mask and no word has measured something and read
 *                nothing, and rendering that as a blank makes it look like a rendering bug.
 *   OVERLAP      duplicates within one set. This is the adapter failing to separate instances,
 *                and it is invisible on a stage where two near-identical masks sit on top of
 *                each other.
 *   REPEAT       the same question asked twice, matched across the two answers. STABILITY, which
 *                is a different claim from duplication and is asserted from different evidence.
 *                Two runs returning five things each is not two runs returning the same five.
 *
 * Every number here is computed IN THIS BROWSER from the mask rasters, and every one of them is
 * badged as such. They are not the producer's measurements and they must never be read as them.
 */
export default function ExtentReadout({ artifact, comparisonArtifact = null, byId,
    focusedInstanceId = null, onFocusInstance }) {
    const instances = useMemo(() => decodeInstances(artifact), [artifact]);
    const comparison = useMemo(
        () => decodeInstances(comparisonArtifact), [comparisonArtifact]);
    const metrics = useMemo(
        () => overlapMetrics(instances, comparisonArtifact ? comparison : null),
        [instances, comparison, comparisonArtifact]);
    const lineage = useMemo(
        () => (artifact && byId ? lineageOf(artifact, byId) : []), [artifact, byId]);

    // The producer's own duplicate list, kept beside the browser's — never instead of it.
    const recordedDuplicates = useMemo(
        () => (artifact?.measurement.payload?.variant === 'extent_set'
            ? (artifact.measurement.payload.duplicates || []) : []),
        [artifact]);
    const disagreement = useMemo(() => {
        const recorded = new Set(recordedDuplicates.map(
            (d) => [...(d.instance_ids || [])].sort().join('|')));
        const derived = new Set(metrics.duplicates.map((d) => [d.a, d.b].sort().join('|')));
        const onlyRecorded = [...recorded].filter((k) => !derived.has(k));
        const onlyDerived = [...derived].filter((k) => !recorded.has(k));
        if (!onlyRecorded.length && !onlyDerived.length) return null;
        return 'The recorded list and this browser’s re-derivation do not agree'
            + `${onlyRecorded.length ? ` — recorded only: ${onlyRecorded.join(', ')}` : ''}`
            + `${onlyDerived.length ? ` — derived only: ${onlyDerived.join(', ')}` : ''}.`
            + ' One of the two is measuring something other than what it says.';
    }, [recordedDuplicates, metrics.duplicates]);

    // A refinement keeps the instance id and moves the revision, so before/after is the same id
    // found at two revisions rather than two shapes that look similar.
    const revised = useMemo(() => {
        if (!artifact || lineage.length < 2) return null;
        const parent = byId?.get(artifact.identity.derived_from?.[0]);
        if (!parent) return null;
        const parentInstances = decodeInstances(parent);
        for (const after of instances) {
            const before = parentInstances.find((p) => p.instance_id === after.instance_id);
            if (before) return { before, after, parent };
        }
        return null;
    }, [artifact, lineage, byId, instances]);

    const change = revised ? beforeAfter(revised.before, revised.after) : null;

    if (!artifact) {
        return (
            <section className="pl-panel" aria-label="Extent readings">
                <div className="pl-panel-head">
                    <h2 className="pl-panel-title">Extent readings</h2>
                </div>
                <EmptyState title="No extent set is active"
                    hint="Duplicates, repeats and revision history are read off the masks. There
                        are none to read." />
            </section>
        );
    }

    return (
        <section className="pl-panel" aria-label="Extent readings" data-extent-readout>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Extent readings</h2>
                <DerivedChip why="every number in this panel was computed in this browser from the
                    mask rasters, to show what the measurement implies. None of it is the
                    producer's measurement." />
            </div>

            {/* ── naming ─────────────────────────────────────────────────── */}
            <div className="pl-field" data-naming-states>
                <span className="pl-label">Naming</span>
                {instances.length === 0 ? (
                    <p className="pl-panel-sub">Nothing was found, so nothing was named.</p>
                ) : (
                    <ul className="pl-list">
                        {instances.map((inst) => (
                            <li key={inst.instance_id}>
                                <button type="button" className="pl-row"
                                    data-naming-row={inst.instance_id}
                                    data-naming-state={inst.naming.state}
                                    aria-pressed={focusedInstanceId === inst.instance_id}
                                    onClick={() => onFocusInstance?.(inst.instance_id)}>
                                    <span className="pl-row-name">{inst.instance_id}</span>
                                    <span className="pl-row-meta">
                                        {inst.naming.text
                                            ? `“${inst.naming.text}” · ${inst.naming.state}`
                                            : 'withheld'}
                                        {inst.confidence !== null
                                            ? ` · geometry ${num(inst.confidence)}` : ''}
                                    </span>
                                </button>
                                <span className="pl-step-why">{inst.naming.note}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {/* ── duplicates within the set ──────────────────────────────── */}
            <div className="pl-field" data-duplicates-block>
                <span className="pl-label">Overlap and duplication, within this set</span>
                <dl className="pl-kv">
                    <dt>as recorded</dt>
                    <dd data-recorded-duplicates={recordedDuplicates.length}>
                        {recordedDuplicates.length
                            ? recordedDuplicates.map((d, i) => (
                                <span key={i} data-recorded-duplicate={
                                    (d.instance_ids || []).join('|')}>
                                    {(d.instance_ids || []).join(' ≈ ')} (IoU {num(d.iou)}){' '}
                                </span>
                            ))
                            : 'the producer recorded no duplicates'}
                    </dd>
                    <dt>pairs compared</dt>
                    <dd data-pairs-compared={metrics.pairs_examined}>{metrics.pairs_examined}</dd>
                    <dt>overlapping</dt>
                    <dd data-overlapping={metrics.overlapping.length}>
                        {metrics.overlapping.length}
                    </dd>
                    <dt>near-duplicate</dt>
                    <dd data-duplicate-pairs={metrics.duplicates.length}>
                        {metrics.duplicates.length
                            ? metrics.duplicates.map((d) => (
                                <span key={`${d.a}-${d.b}`} data-duplicate-pair={`${d.a}|${d.b}`}>
                                    {d.a} ≈ {d.b} (IoU {num(d.iou)}){' '}
                                </span>
                            ))
                            : `none at IoU ≥ ${metrics.duplicate_threshold}`}
                    </dd>
                </dl>
                <p className="pl-panel-sub" data-threshold-note>
                    A duplicate is a THRESHOLD and not a fact. The first row is the producer’s own
                    list, on the record; the rest is this browser re-deriving it at IoU ≥{' '}
                    {metrics.duplicate_threshold}. They are shown together so a disagreement is
                    visible rather than resolved silently in favour of whichever ran last.
                </p>
                {disagreement ? (
                    <p className="pl-error" role="alert" data-duplicate-disagreement>
                        {disagreement}
                    </p>
                ) : null}
                {metrics.duplicates.length ? (
                    <p className="pl-panel-sub">
                        Two instances this close are one thing the adapter failed to separate, or
                        two things it should not have merged. On the stage they sit on top of each
                        other and look like one confident mask.
                    </p>
                ) : null}
            </div>

            {/* ── repeat, across two runs ────────────────────────────────── */}
            {comparisonArtifact ? (
                <div className="pl-field" data-repeat-block>
                    <span className="pl-label">
                        Repeat — this set against {comparisonArtifact.identity.artifact_id}
                    </span>
                    {metrics.refusal ? (
                        <p className="pl-panel-sub" data-repeat-refused>{metrics.refusal}</p>
                    ) : (
                        <dl className="pl-kv">
                            <dt>matched</dt>
                            <dd data-repeat-matched={metrics.repeats.matched.length}>
                                {metrics.repeats.matched.length} of {instances.length} at IoU ≥ 0.5
                            </dd>
                            <dt>unmatched here</dt>
                            <dd data-repeat-unmatched={metrics.repeats.unmatched.length}>
                                {metrics.repeats.unmatched.length
                                    ? metrics.repeats.unmatched.map((m) => m.a).join(', ')
                                    : 'none'}
                            </dd>
                            <dt>only in the other</dt>
                            <dd data-repeat-only-other={metrics.repeats.only_in_other.length}>
                                {metrics.repeats.only_in_other.length
                                    ? metrics.repeats.only_in_other.join(', ')
                                    : 'none'}
                            </dd>
                            <dt>mean IoU</dt>
                            <dd data-repeat-mean-iou>{num(metrics.repeats.mean_iou)}</dd>
                        </dl>
                    )}
                    <p className="pl-panel-sub">
                        Stability, not duplication. Two runs returning five instances each is not
                        two runs returning the same five, and only the matching says which.
                    </p>
                </div>
            ) : null}

            {/* ── revision and lineage ───────────────────────────────────── */}
            <div className="pl-field" data-lineage-block>
                <span className="pl-label">Revision and lineage</span>
                {lineage.length <= 1 ? (
                    <p className="pl-panel-sub" data-no-lineage>
                        Taken from the image directly. Nothing was derived from anything.
                    </p>
                ) : (
                    <ol className="pl-list" data-lineage>
                        {lineage.map((node) => (
                            <li key={node.artifact_id} className="pl-step"
                                data-lineage-node={node.artifact_id}>
                                <span className="pl-step-op">
                                    <code>{node.operation}</code> · {node.artifact_id}
                                </span>
                                <span className="pl-step-why">
                                    {node.instances.map((i) => (
                                        <span key={i.instance_id}
                                            data-lineage-instance={i.instance_id}
                                            data-geometry-rev={i.geometry_rev === null
                                                ? 'none' : i.geometry_rev}>
                                            {i.instance_id}
                                            {i.geometry_rev === null
                                                ? ' (session-local, no revision)'
                                                : ` @rev ${i.geometry_rev}`}{' '}
                                        </span>
                                    ))}
                                </span>
                            </li>
                        ))}
                    </ol>
                )}
                {change ? (
                    <div data-before-after>
                        {change.available ? (
                            <dl className="pl-kv">
                                <dt>added</dt>
                                <dd data-added-fraction>{num(change.added_fraction)} of the frame</dd>
                                <dt>removed</dt>
                                <dd data-removed-fraction>
                                    {num(change.removed_fraction)} of the frame
                                </dd>
                                <dt>net</dt>
                                <dd data-net-fraction>{num(change.net_fraction)}</dd>
                                <dt>identity</dt>
                                <dd data-identity-preserved="true">
                                    the same instance at a later revision — the id did not change,
                                    so this is not a new thing that resembles the old one
                                </dd>
                            </dl>
                        ) : (
                            <p className="pl-panel-sub" data-before-after-refused>{change.why}</p>
                        )}
                    </div>
                ) : null}
            </div>
        </section>
    );
}
