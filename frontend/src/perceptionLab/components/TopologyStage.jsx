import React, { useMemo, useRef, useState } from 'react';
import useStageGeometry, { useNaturalSize } from '../../differential/useStageGeometry';
import { ringsToPath } from '../../lib/maskGeometry';
import { BasisChip, DerivedChip, EmptyState, EpistemicChip } from './Chips';
import { projectNegativeSpace, projectRelationSet } from '../topologyView';
import { num } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — where a relation actually is.
 *
 * A topology artifact says `contact_pixels: 812` and carries no geometry at all. `projection.hints`
 * is clamped to seven presentational keys, so the band cannot arrive through there either. Which
 * leaves two options: show the number and never show where it is, or compute the picture here.
 *
 * This computes it, and then spends most of its markup making sure the picture is not mistaken for
 * the measurement. Every layer is `derived: true`, every layer says `computed_by: lab_browser`, and
 * where the derived number and the producer's number can be compared, both are printed side by
 * side with the disagreement — if any — stated as a disagreement rather than reconciled.
 *
 * THE BASIS COMES FROM THE RELATION. A relation measured on boxes is drawn on boxes. Drawing it on
 * masks because masks look better would show a per-pixel picture of an interpretive number, which
 * is the exact inversion the WAVE2.5 ruling exists to prevent.
 */
export default function TopologyStage({ artifact, source, session, byId,
    focusedRelationId = null, onFocusRelation, stageRef: externalRef }) {
    const localRef = useRef(null);
    const stageRef = externalRef || localRef;
    const [loaded, onImgLoad] = useNaturalSize();
    const declared = useMemo(
        () => (session?.source
            ? { w: session.source.natural_width, h: session.source.natural_height } : null),
        [session?.source]);
    const natural = loaded || declared;
    useStageGeometry(stageRef, natural);

    const [showAll, setShowAll] = useState(true);
    const relations = useMemo(
        () => projectRelationSet(artifact, byId), [artifact, byId]);
    const wash = useMemo(() => projectNegativeSpace(artifact, byId), [artifact, byId]);

    if (!artifact || (!relations.length && !wash)) {
        return (
            <section className="pl-panel" aria-label="Topology stage">
                <div className="pl-panel-head">
                    <h2 className="pl-panel-title">Where the relation is</h2>
                </div>
                <EmptyState title="No relation is on the image"
                    hint="Measure a relation between two extents. The number will land here as a
                        band, an intersection or a clearance — drawn in this browser, and
                        labelled as drawn." />
            </section>
        );
    }

    const shown = focusedRelationId && !showAll
        ? relations.filter((r) => r.relation_id === focusedRelationId)
        : relations;

    return (
        <section className="pl-panel" aria-label="Topology stage" data-topology-stage>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Where the relation is</h2>
                <span className="pl-chiprow">
                    <DerivedChip why="every band, intersection and clearance on this image was
                        computed in this browser from the endpoint masks. The measurement is the
                        number in the list; this is a picture of where it lives." />
                    {relations.length > 1 ? (
                        <button type="button" className="pl-btn pl-btn--quiet" data-show-all
                            aria-pressed={showAll} onClick={() => setShowAll((v) => !v)}>
                            {showAll ? `all ${relations.length} drawn` : 'focused only'}
                        </button>
                    ) : null}
                </span>
            </div>

            <div className="pl-stage" ref={stageRef} data-view="mask">
                <img src={source?.photo_url} alt="" onLoad={onImgLoad} draggable={false} />
                {natural ? (
                    <svg className="pl-svg pl-svg--passive"
                        viewBox={`0 0 ${natural.w} ${natural.h}`}
                        preserveAspectRatio="xMidYMid meet" aria-hidden="true">
                        {wash?.derived?.available ? (
                            <g data-layer="scalar_wash" data-derived="true">
                                {wash.derived.cells.map((cell, i) => (
                                    <rect key={i} className="pl-wash-cell"
                                        x={cell.x * natural.w} y={cell.y * natural.h}
                                        width={cell.w * natural.w} height={cell.h * natural.h}
                                        fill="currentColor" opacity={0.06 + cell.intensity * 0.5} />
                                ))}
                            </g>
                        ) : null}
                        {shown.map((rel) => (
                            <RelationLayer key={rel.relation_id} rel={rel} natural={natural}
                                focused={focusedRelationId === rel.relation_id}
                                onFocus={onFocusRelation} />
                        ))}
                    </svg>
                ) : null}
            </div>

            <div className="pl-stage-legend">
                <span className="pl-swatch pl-swatch--band" aria-hidden="true" />
                <span>contact band</span>
                <span className="pl-swatch pl-swatch--inter" aria-hidden="true" />
                <span>intersection</span>
                <span>— endpoint pair, arrowed only where the relation is directed</span>
            </div>

            {shown.some((r) => !r.drawable) ? (
                <div className="pl-field" data-undrawable-relations>
                    <span className="pl-label">Measured, and not placeable on the image</span>
                    <ul className="pl-list">
                        {shown.filter((r) => !r.drawable).map((r) => (
                            <li key={r.relation_id} className="pl-step-why"
                                data-undrawable={r.relation_id}>
                                <code>{r.kind}</code> — {r.why}
                            </li>
                        ))}
                    </ul>
                    <p className="pl-panel-sub">
                        The numbers stand. Only the picture is missing, and the difference between
                        those two is the whole reason this panel says which.
                    </p>
                </div>
            ) : null}

            {wash ? <WashNote wash={wash} /> : null}
        </section>
    );
}

/** One relation, drawn as the kind of thing it is. */
function RelationLayer({ rel, natural, focused, onFocus }) {
    if (!rel.drawable) return null;
    const p = rel.projection;
    const cls = p.projection_kind === 'contact_band' ? 'pl-band'
        : p.projection_kind === 'intersection_area' ? 'pl-intersection' : null;
    const anchors = rel.endpoints?.available ? rel.endpoints : null;
    const from = p.from || anchors?.from;
    const to = p.to || anchors?.to;

    return (
        <g className="pl-layer" data-relation-layer={rel.relation_id}
            data-projection-kind={p.projection_kind}
            data-derived="true" data-basis={rel.basis}
            data-focused={focused ? 'true' : 'false'}
            data-stale={String(rel.stale)}
            onClick={() => onFocus?.(rel.relation_id)}>
            {cls && p.rings.length ? (
                <path className={cls} fillRule="evenodd" vectorEffect="non-scaling-stroke"
                    d={ringsToPath(p.rings, natural.w, natural.h)} />
            ) : null}
            {from && to ? (
                <>
                    <line className="pl-endpoint-line" vectorEffect="non-scaling-stroke"
                        x1={from.x * natural.w} y1={from.y * natural.h}
                        x2={to.x * natural.w} y2={to.y * natural.h}
                        markerEnd={rel.directed ? 'url(#pl-arrow)' : undefined}
                        data-directed={String(rel.directed)} />
                    <circle className="pl-endpoint-dot" r={Math.max(3, natural.w * 0.005)}
                        cx={from.x * natural.w} cy={from.y * natural.h} data-endpoint="source" />
                    {rel.directed ? (
                        <ArrowHead from={from} to={to} natural={natural} />
                    ) : (
                        <circle className="pl-endpoint-dot" r={Math.max(3, natural.w * 0.005)}
                            cx={to.x * natural.w} cy={to.y * natural.h} data-endpoint="target" />
                    )}
                </>
            ) : null}
        </g>
    );
}

/**
 * An arrowhead, and only where the relation is directed.
 *
 * `meets` is symmetric. Drawing it with an arrow would assert an asymmetry the organ did not
 * measure, and a person reading the picture would come away believing something no number said.
 */
function ArrowHead({ from, to, natural }) {
    const x1 = from.x * natural.w; const y1 = from.y * natural.h;
    const x2 = to.x * natural.w; const y2 = to.y * natural.h;
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const size = Math.max(8, natural.w * 0.014);
    const pts = [
        [x2, y2],
        [x2 - size * Math.cos(angle - Math.PI / 7), y2 - size * Math.sin(angle - Math.PI / 7)],
        [x2 - size * Math.cos(angle + Math.PI / 7), y2 - size * Math.sin(angle + Math.PI / 7)],
    ].map(([x, y]) => `${x},${y}`).join(' ');
    return <polygon className="pl-endpoint-dot" data-arrowhead points={pts} />;
}

/** What the wash is, and what it is not. */
function WashNote({ wash }) {
    return (
        <div className="pl-field" data-wash-note>
            <span className="pl-label">Negative space</span>
            {!wash.measured.available ? (
                <p className="pl-panel-sub" data-measured-field-absent>
                    {wash.measured.why}
                </p>
            ) : null}
            {wash.derived.available ? (
                <>
                    <span className="pl-chiprow">
                        <DerivedChip why="a Chebyshev distance transform run in this browser over
                            the complement of the figure masks, truncated at the same
                            max_distance_used the artifact recorded." />
                    </span>
                    <p className="pl-panel-sub">
                        The wash on the image was <strong>derived here</strong>, from the figure
                        masks. It is not the measured field — that is behind{' '}
                        <code>field_ref</code> and this page cannot read it.
                    </p>
                    {wash.derived.agrees_with_statistics ? (
                        <dl className="pl-kv" data-wash-agreement>
                            <dt>agrees</dt>
                            <dd data-wash-agrees={
                                String(wash.derived.agrees_with_statistics.agrees)}>
                                {wash.derived.agrees_with_statistics.agrees
                                    ? 'the derived field’s statistics match the recorded ones, '
                                        + 'which is the only check this side of the wire can make'
                                    : 'THE DERIVED FIELD DOES NOT MATCH THE RECORDED STATISTICS. '
                                        + 'One of the two is measuring something else.'}
                            </dd>
                        </dl>
                    ) : null}
                </>
            ) : (
                <p className="pl-panel-sub" data-wash-underivable>{wash.derived.why}</p>
            )}
        </div>
    );
}

/** The typed list, kept typed. Exported for the inspector column. */
export function RelationRow({ rel, focused, onFocus }) {
    return (
        <li className="pl-step" data-relation-row={rel.relation_id}
            data-relation-kind={rel.kind} data-drawable={String(rel.drawable)}>
            <button type="button" className="pl-row" data-focus-relation={rel.relation_id}
                aria-pressed={focused} onClick={() => onFocus?.(rel.relation_id)}>
                <span className="pl-row-name" data-relation-sentence>{rel.sentence}</span>
                <span className="pl-row-meta" data-relation-direction={
                    rel.directed ? 'directed' : 'symmetric'}>
                    {rel.directed ? 'directed' : 'symmetric'}
                </span>
            </button>
            {/*
              * THE SENTENCE USES THE NAME; THE IDENTITY IS ALSO SHOWN.
              *
              * "the disc is inside the frame" is what a person can read, and a name is
              * interpretive — two instances can carry the same word. So the endpoint ids sit
              * beside it, in the direction they were measured, because a relation whose endpoints
              * are only identified by their labels cannot be checked against the record.
              */}
            <span className="pl-step-why" data-endpoint-identity>
                <code data-endpoint-source={rel.source.ref?.instance_id || ''}>
                    {rel.source.ref
                        ? `${rel.source.ref.artifact_id}#${rel.source.ref.instance_id || '*'}`
                        : 'absent'}
                </code>
                {rel.directed ? ' → ' : ' — '}
                <code data-endpoint-target={rel.target.ref?.instance_id || ''}>
                    {rel.target.ref
                        ? `${rel.target.ref.artifact_id}#${rel.target.ref.instance_id || '*'}`
                        : 'absent'}
                </code>
                {rel.source.ref?.scope === 'canonical' || rel.target.ref?.scope === 'canonical'
                    ? ' · cites a canonical region' : ''}
            </span>
            <span className="pl-chiprow">
                <span className="pl-chip" data-kind={rel.kind}>{rel.kind}</span>
                <BasisChip basis={rel.basis} />
                <EpistemicChip status={rel.epistemic_status} />
                {rel.stale ? (
                    <span className="pl-stale" data-relation-stale>
                        stale — an endpoint has moved since this was measured
                    </span>
                ) : null}
                {rel.source.state === 'dangling' || rel.target.state === 'dangling' ? (
                    <span className="pl-dangling" data-relation-dangling>
                        dangling endpoint
                    </span>
                ) : null}
            </span>
            <span className="pl-step-why" data-relation-measurements>
                {Object.entries(rel.measurements).length
                    ? Object.keys(rel.measurements).sort()
                        .map((k) => `${k} ${num(rel.measurements[k])}`).join(' · ')
                    : 'no scalar measurement'}
            </span>
            {rel.agreement ? (
                <span className="pl-step-why" data-agreement={rel.agreement.quantity}
                    data-agrees={String(rel.agreement.agrees)}>
                    {rel.agreement.quantity}: recorded {num(rel.agreement.measured)}, this browser
                    {' '}derived {num(rel.agreement.derived)}
                    {rel.agreement.agrees
                        ? ' — they agree'
                        : ' — THEY DO NOT AGREE. The drawing and the number are describing '
                            + 'different things.'}
                </span>
            ) : null}
            {!rel.drawable ? (
                <span className="pl-step-why" data-relation-undrawable>{rel.why}</span>
            ) : null}
        </li>
    );
}
