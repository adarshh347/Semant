import React from 'react';
import { legendFor, EVIDENCE_TREATMENT } from '../layerModel';

/**
 * PERCEPTUAL-FORMS-001E — the legend, which is the deliverable.
 *
 * Every rule in the build brief's "truth rules" section is a rule about what a person can read
 * beside a drawing, and this is where they are read. It is not a key: a key says "solid means
 * measured" once and leaves a person to work out which of eleven shapes is solid. This is ONE ROW
 * PER LAYER, in drawing order, each row naming the source form, the record, the evidence class,
 * the coordinate system, the basis, the hypothesis, the part and the threshold.
 *
 * IT IS ALSO THE KEYBOARD PATH. SVG shapes are awkward to focus and worse to describe; the rows
 * are ordinary buttons, so Tab reaches every layer, Enter focuses it on the stage, and a screen
 * reader gets the whole declaration as text rather than a `<path>`. The shapes remain clickable
 * for the mouse. Nothing on the stage is reachable ONLY by pointing.
 *
 * A row for an absent layer says why. That row is often the most informative thing on the page —
 * "no committed fixture carries art_extent_1#inst_piazza" is a finding about the record, and it
 * is the finding a blank stage would have hidden.
 */

const SWATCH = {
    measured: 'M2 8 h20',
    derived: 'M2 8 h20',
    inferred: 'M2 8 h20',
    hypothetical: 'M2 8 h20',
    absent: 'M2 8 h20',
};

/** The treatment, drawn. The same dash the stage uses, at legend scale. */
function Swatch({ evidence }) {
    const t = EVIDENCE_TREATMENT[evidence];
    return (
        <svg className="pl-fm-swatch" width="26" height="16" viewBox="0 0 26 16" aria-hidden="true"
            data-evidence={evidence}>
            <rect className="pl-fm-swatch-fill" x="2" y="3" width="22" height="10"
                fillOpacity={t.fillOpacity} />
            <path className="pl-fm-swatch-rule" d={SWATCH[evidence]}
                strokeDasharray={t.dash ?? undefined} strokeWidth={t.strokeWidth || 1} />
        </svg>
    );
}

const value = (v) => (v === null || v === undefined ? null : String(v));

function Row({ row, focused, onFocus, onToggle, hidden }) {
    const parts = [
        row.form && ['form', row.form],
        row.source && ['record', sourceLabel(row.source)],
        ['space', row.coordinate_system],
        row.raster && ['raster', `${row.raster.h}×${row.raster.w}`],
        row.basis && ['basis', row.basis],
        row.epistemic_status && ['status', row.epistemic_status],
        row.part && ['part', row.part],
        row.hypothesis_id && ['hypothesis', row.hypothesis_id],
        row.calibration?.state && ['calibration', row.calibration.state],
    ].filter(Boolean);

    return (
        <li className="pl-fm-legendrow" data-layer={row.layer_id} data-evidence={row.evidence}
            data-focused={focused ? 'true' : 'false'} data-hidden={hidden ? 'true' : 'false'}>
            <button
                type="button"
                className="pl-fm-legendbtn"
                aria-pressed={focused}
                data-focus-layer={row.layer_id}
                onClick={() => onFocus?.(focused ? null : row.layer_id)}
            >
                <Swatch evidence={row.evidence} />
                <span className="pl-fm-legendname">{row.label}</span>
                {/* THE WORD. The third redundant channel, and the only one that survives being
                    read aloud or printed in one colour. */}
                <span className="pl-fm-evidence" data-evidence-word={row.evidence}>
                    {row.word}
                </span>
            </button>
            {onToggle ? (
                <button
                    type="button"
                    className="pl-fm-legendtoggle"
                    aria-pressed={!hidden}
                    data-toggle-layer={row.layer_id}
                    title={hidden ? 'draw this layer' : 'hide this layer'}
                    onClick={() => onToggle(row.layer_id)}
                >
                    {hidden ? 'show' : 'hide'}
                </button>
            ) : null}

            <dl className="pl-fm-decl" data-declaration={row.layer_id}>
                {parts.map(([k, v]) => (
                    <React.Fragment key={k}>
                        <dt data-decl-key={k}>{k}</dt>
                        <dd data-decl-value={k}>{v}</dd>
                    </React.Fragment>
                ))}
                {row.binarized ? (
                    <>
                        <dt data-decl-key="threshold">threshold</dt>
                        {/* A BINARIZED LAYER CANNOT REACH THIS COMPONENT WITHOUT ONE —
                            `assertLayer` refuses to build it. This row is where the number a
                            person needs actually appears. */}
                        <dd data-decl-value="threshold" data-threshold={row.threshold.value}>
                            {row.threshold.value} — {row.threshold.source}
                        </dd>
                    </>
                ) : null}
            </dl>

            <p className="pl-fm-sentence" data-evidence-sentence={row.evidence}>
                {row.sentence}
            </p>
            {row.why_absent ? (
                <p className="pl-fm-why" data-why-absent={row.layer_id}>{row.why_absent}</p>
            ) : null}
            {row.note ? <p className="pl-fm-note" data-layer-note={row.layer_id}>{row.note}</p> : null}
        </li>
    );
}

const sourceLabel = (s) => {
    if (typeof s === 'string') return s;
    if (s.artifact_id && s.instance_id) return `${s.artifact_id}#${s.instance_id}`;
    if (s.relation_id) return s.relation_id;
    if (s.locus_id) return s.locus_id;
    if (s.path_id) return s.path_id;
    if (s.intersection_id) return s.intersection_id;
    if (s.edge_id) return s.edge_id;
    if (s.hole_id) return s.hole_id;
    if (s.region_id) return `${s.region_id} (canonical Region)`;
    if (s.artifact_id) return s.artifact_id;
    return JSON.stringify(s);
};

export default function LayerLegend({
    layers = [], focusId = null, onFocus = null, hidden = null, onToggle = null,
    measurementsFor = null,
}) {
    const rows = legendFor(layers);
    if (!rows.length) {
        return (
            <div className="pl-fm-legend" data-legend-empty="true">
                <p className="pl-fm-why">
                    This view produced no layer at all — not even an absent one. That is a bug in
                    the renderer, not an empty record: every view in this laboratory is required to
                    return something that says what it looked at.
                </p>
            </div>
        );
    }
    return (
        <div className="pl-fm-legend" data-legend-rows={rows.length}>
            <h3 className="pl-fm-legendtitle">
                What is drawn
                <span className="pl-fm-legendcount" data-legend-count={rows.length}>
                    {rows.length} layer{rows.length === 1 ? '' : 's'}
                </span>
            </h3>
            <ul className="pl-fm-legendlist">
                {rows.map((row) => (
                    <React.Fragment key={row.layer_id}>
                        <Row
                            row={row}
                            focused={focusId === row.layer_id}
                            onFocus={onFocus}
                            onToggle={onToggle}
                            hidden={hidden?.has?.(row.layer_id)}
                        />
                        {measurementsFor?.(row.layer_id) ? (
                            <li className="pl-fm-measurerow" data-measurements={row.layer_id}>
                                {measurementsFor(row.layer_id)}
                            </li>
                        ) : null}
                    </React.Fragment>
                ))}
            </ul>
        </div>
    );
}

/**
 * The measurements a layer carries, including a derived-versus-recorded disagreement.
 *
 * Split out because the interesting case is not the numbers, it is `agreement`: a `{derived,
 * measured, delta, agrees}` object means this browser computed something the producer also
 * computed, and the two are printed side by side WITH the word "disagrees" when they do. Hiding
 * that behind a tolerance would make the surface useless for the thing it is for.
 */
export function Measurements({ measurements }) {
    if (!measurements) return null;
    const entries = Object.entries(measurements).filter(([, v]) => v !== null && v !== undefined);
    if (!entries.length) return null;
    return (
        <dl className="pl-fm-measure">
            {entries.map(([k, v]) => {
                if (k === 'agreement' && typeof v === 'object') {
                    return (
                        <React.Fragment key={k}>
                            <dt>drawn here vs recorded</dt>
                            <dd data-agreement={v.agrees ? 'agrees' : 'disagrees'}
                                data-derived={v.derived} data-measured={v.measured}>
                                {v.derived} vs {v.measured} — {v.agrees ? 'agrees' : 'DISAGREES'}
                                {' '}(δ {Math.round(v.delta * 1000) / 1000})
                            </dd>
                        </React.Fragment>
                    );
                }
                return (
                    <React.Fragment key={k}>
                        <dt>{k.replace(/_/g, ' ')}</dt>
                        <dd data-measure={k}>{value(typeof v === 'object' ? JSON.stringify(v) : v)}</dd>
                    </React.Fragment>
                );
            })}
        </dl>
    );
}
