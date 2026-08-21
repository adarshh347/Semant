import React from 'react';
import FormStage from './FormStage';
import FormDiagram from './FormDiagram';
import LayerLegend, { Measurements } from './LayerLegend';

/**
 * PERCEPTUAL-FORMS-001E — one component per SURFACE, and the dispatcher that picks between them.
 *
 * Five surfaces, and each is a different answer to "where does this belong":
 *
 *   stage     one letterboxed image stage.
 *   compare   several labelled stages, side by side. NEVER superimposed — which is what makes it
 *             the right surface for alternatives and for before/after, because both are things
 *             that must not be merged.
 *   sheet     a grid of cropped thumbnails, one per member.
 *   diagram   node-link or matrix, in diagram space.
 *   panel     measurements and sentences. Not a fallback: several forms measure things that have
 *             no shape, and a lab that only rendered what could be drawn would drop them.
 *
 * THE LEGEND IS NOT OPTIONAL ON ANY OF THEM. It renders under every surface, including `panel`,
 * because the declaration is what makes a reading trustworthy and a panel of numbers with no
 * provenance is the same problem as an undeclared drawing.
 */

function ComparePanes({ sides, natural, focusId, onFocus }) {
    return (
        <div className="pl-fm-compare" data-compare-sides={sides.length}>
            {sides.map((side) => (
                <figure key={side.key} className="pl-fm-pane" data-pane={side.key}>
                    <figcaption className="pl-fm-panecap" data-pane-label={side.key}>
                        {side.label}
                    </figcaption>
                    <FormStage
                        layers={side.layers}
                        natural={natural}
                        focusId={focusId}
                        onFocus={onFocus}
                        label={side.label}
                        compact
                    />
                </figure>
            ))}
        </div>
    );
}

function ContactSheet({ items, natural, focusId, onFocus }) {
    return (
        <div className="pl-fm-sheet" data-sheet-items={items.length}>
            {items.map(({ layer, crop }) => (
                <figure key={layer.layer_id} className="pl-fm-thumb" data-thumb={layer.layer_id}
                    data-evidence={layer.evidence}
                    data-cropped={crop ? 'true' : 'false'}>
                    <FormStage
                        layers={[layer]}
                        natural={natural}
                        crop={crop}
                        focusId={focusId}
                        onFocus={onFocus}
                        showGrid={false}
                        label={layer.label}
                        compact
                    />
                    <figcaption className="pl-fm-thumbcap">
                        {layer.label}
                        {/* A CROPPED THUMBNAIL IS A ZOOM, and a zoom that does not say its scale
                            makes a 1% instance look the same size as a 40% one. */}
                        {crop ? (
                            <span className="pl-fm-thumbscale" data-crop-fraction={crop.w * crop.h}>
                                {Math.round(crop.w * 100)}% × {Math.round(crop.h * 100)}% of frame
                            </span>
                        ) : (
                            <span className="pl-fm-thumbscale">not drawn</span>
                        )}
                    </figcaption>
                </figure>
            ))}
        </div>
    );
}

function ReadingPanel({ layers }) {
    const readings = layers.filter((l) => l.draw?.kind === 'text');
    if (!readings.length) return null;
    return (
        <div className="pl-fm-readings" data-readings={readings.length}>
            {readings.map((l) => (
                <section key={l.layer_id} className="pl-fm-reading" data-reading={l.layer_id}
                    data-evidence={l.evidence}>
                    <h4 className="pl-fm-readingtitle">{l.label}</h4>
                    <dl className="pl-fm-readingrows">
                        {(l.draw.rows || []).map((row, i) => (
                            <React.Fragment key={`${row.label}-${i}`}>
                                <dt data-row-label={row.label}>{row.label}</dt>
                                <dd data-row-value={row.label}>
                                    {row.value === null || row.value === undefined
                                        ? 'not recorded' : String(row.value)}
                                    {row.strength !== undefined && row.strength !== null ? (
                                        <span className="pl-fm-strength" data-strength={row.strength}>
                                            strength {row.strength}
                                        </span>
                                    ) : null}
                                    {row.strength === null ? (
                                        // A ground with no strength is not a weak ground. It is a
                                        // ground the record declined to weigh, and printing 0
                                        // would be inventing a number.
                                        <span className="pl-fm-strength" data-strength="unweighed">
                                            not weighed
                                        </span>
                                    ) : null}
                                    {row.detail ? (
                                        <span className="pl-fm-rowdetail">{row.detail}</span>
                                    ) : null}
                                    {row.relations !== undefined ? (
                                        <span className="pl-fm-rowdetail"
                                            data-row-relations={row.relations}>
                                            {row.relations} relation
                                            {row.relations === 1 ? '' : 's'} under it
                                        </span>
                                    ) : null}
                                </dd>
                            </React.Fragment>
                        ))}
                    </dl>
                    {l.note ? <p className="pl-fm-note" data-reading-note={l.layer_id}>{l.note}</p> : null}
                </section>
            ))}
        </div>
    );
}

export default function FormSurface({
    view, layers = [], sides = null, items = null, natural, focusId = null, onFocus = null,
    hidden = null, onToggle = null, error = null, draft = null,
}) {
    const shown = hidden ? layers.filter((l) => !hidden.has(l.layer_id)) : layers;
    const surface = view?.surface ?? 'stage';

    const body = (() => {
        if (error) {
            return (
                <p className="pl-fm-refused" data-render-error="true">{error}</p>
            );
        }
        if (surface === 'compare' && sides) {
            return <ComparePanes sides={sides} natural={natural} focusId={focusId}
                onFocus={onFocus} />;
        }
        if (surface === 'sheet' && items) {
            return <ContactSheet items={items} natural={natural} focusId={focusId}
                onFocus={onFocus} />;
        }
        if (surface === 'diagram') {
            return <FormDiagram layers={shown} focusId={focusId} onFocus={onFocus} />;
        }
        if (surface === 'panel') {
            return <ReadingPanel layers={shown} />;
        }
        return (
            <>
                <FormStage layers={shown} natural={natural} focusId={focusId} onFocus={onFocus}
                    label={view?.label ?? 'form stage'} draft={draft} />
                <ReadingPanel layers={shown} />
            </>
        );
    })();

    return (
        <div className="pl-fm-surface" data-surface={surface} data-view={view?.key}>
            {body}
            <LayerLegend
                layers={layers}
                focusId={focusId}
                onFocus={onFocus}
                hidden={hidden}
                onToggle={onToggle}
                measurementsFor={(id) => {
                    const l = layers.find((x) => x.layer_id === id);
                    return l?.measurements
                        ? <Measurements measurements={l.measurements} /> : null;
                }}
            />
        </div>
    );
}
