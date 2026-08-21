import React, { useMemo, useRef } from 'react';
import useStageGeometry, { useNaturalSize } from '../../../differential/useStageGeometry';
import { EVIDENCE_TREATMENT, isStageLayer } from '../layerModel';

/**
 * PERCEPTUAL-FORMS-001E — the image stage, and the four rules it enforces in markup.
 *
 * THE LETTERBOX CONTRACT IS NOT REIMPLEMENTED, it is obeyed: `viewBox` in natural pixels plus
 * `preserveAspectRatio="xMidYMid meet"`, which is exactly what `object-fit: contain` does, which
 * is what `RegionOverlay` and `useStageGeometry` already agree on across this application. A
 * surface that invents its own version of this is how a mask lands on the wrong part of a face,
 * and this laboratory exists to catch that class of error rather than to reproduce it.
 *
 * WHY NOT `RegionOverlay` ITSELF. It draws rings, and it draws them through the Region ontology —
 * `selectedId`, `activeId`, `litIds`, a proposal, a prompt. The layers here are rings AND cell
 * fields AND point sets AND polylines AND arrowheads, and each one carries an evidence class that
 * has to reach the markup. Reusing the overlay would mean either widening a component four other
 * surfaces depend on, or flattening every form to rings. So the geometry CONTRACT is shared and
 * the drawing is not, and the two lines above are the whole of what must not diverge.
 *
 * FOUR RULES, ENFORCED HERE RATHER THAN TRUSTED:
 *
 *   1. A DIAGRAM LAYER IS REFUSED. `coordinate_system: 'diagram'` means a graph node, and a graph
 *      node has no location. Letterboxing one onto the image would put it at a pixel and a person
 *      would read that pixel as a place.
 *   2. EVERY SHAPE CARRIES ITS EVIDENCE CLASS in `data-evidence`, and its dash and fill pattern
 *      come from `EVIDENCE_TREATMENT` — not from the caller. Three redundant channels before
 *      colour: turn the stylesheet off and inferred is still hatched and still dashed.
 *   3. A CELL FIELD IS DRAWN AS CELLS, with every boundary visible. A smooth gradient over a 4×4
 *      measurement is a claim about resolution that the measurement does not support.
 *   4. AN ARROWHEAD IS DRAWN ONLY WHERE THE LAYER SAYS `arrow`. An arrow on an undirected
 *      relation asserts an asymmetry nobody measured.
 *
 * COLOUR IS USED FOR IDENTITY, NEVER FOR EVIDENCE. Sibling layers rotate through the palette's
 * six hues so a person can tell instance 3 from instance 4; what KIND of claim each one is comes
 * from the dash, the pattern and the word in the legend.
 */

/** The six-hue family, as identity slots. Order is stable so a screenshot is reproducible. */
const HUES = ['plum', 'amethyst', 'clay', 'indigo', 'mulberry', 'lilac'];

const dashFor = (l) => EVIDENCE_TREATMENT[l.evidence].dash ?? undefined;
const patternFor = (l) => EVIDENCE_TREATMENT[l.evidence].pattern;

const ringsToPath = (rings, w, h) => rings
    .map((ring) => `${ring.map(([x, y], i) => `${i ? 'L' : 'M'}${x * w} ${y * h}`).join(' ')}Z`)
    .join(' ');

/**
 * The fill patterns, defined once per stage.
 *
 * Ids are namespaced with the stage's own id because two stages on one page (a compare view) would
 * otherwise share a `<defs>` and the second would silently reference the first's.
 */
function Patterns({ ns }) {
    return (
        <defs>
            <pattern id={`${ns}-hatch-45`} className="pl-fm-pattern" patternUnits="userSpaceOnUse"
                width="10" height="10" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="10" />
            </pattern>
            <pattern id={`${ns}-hatch-135`} className="pl-fm-pattern" patternUnits="userSpaceOnUse"
                width="10" height="10" patternTransform="rotate(135)">
                <line x1="0" y1="0" x2="0" y2="10" />
            </pattern>
            <pattern id={`${ns}-dots`} className="pl-fm-pattern" patternUnits="userSpaceOnUse"
                width="8" height="8">
                <circle cx="2" cy="2" r="1.2" />
            </pattern>
            <marker id={`${ns}-arrow`} className="pl-fm-arrow" viewBox="0 0 10 10"
                refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" />
            </marker>
        </defs>
    );
}

function RingShape({ layer, natural, ns, dimmed, focused, onFocus }) {
    const { rings, filled } = layer.draw;
    if (!rings?.length) return null;
    const pattern = patternFor(layer);
    const d = ringsToPath(rings, natural.w, natural.h);
    return (
        <g className="pl-fm-shape" data-layer={layer.layer_id} data-evidence={layer.evidence}
            data-dimmed={dimmed ? 'true' : 'false'} data-focused={focused ? 'true' : 'false'}
            onClick={() => onFocus?.(layer.layer_id)}>
            {/* The pattern goes UNDER the tinted fill so both read: the hatch says what kind of
                claim this is, the tint says which layer it is. */}
            {filled && pattern ? (
                <path d={d} fillRule="evenodd" fill={`url(#${ns}-${pattern})`}
                    className="pl-fm-hatch" />
            ) : null}
            <path
                className="pl-fm-ring"
                d={d}
                fillRule="evenodd"
                data-filled={filled ? 'true' : 'false'}
                fillOpacity={filled ? EVIDENCE_TREATMENT[layer.evidence].fillOpacity : 0}
                strokeWidth={EVIDENCE_TREATMENT[layer.evidence].strokeWidth}
                strokeDasharray={dashFor(layer)}
                vectorEffect="non-scaling-stroke"
            />
        </g>
    );
}

function CellShape({ layer, natural, ns, dimmed, focused, onFocus }) {
    const { cells } = layer.draw;
    if (!cells?.length) return null;
    const pattern = patternFor(layer);
    return (
        <g className="pl-fm-shape pl-fm-cells" data-layer={layer.layer_id}
            data-evidence={layer.evidence} data-binarized={layer.binarized ? 'true' : 'false'}
            data-cells={cells.length} data-raster={`${layer.raster?.h}x${layer.raster?.w}`}
            data-dimmed={dimmed ? 'true' : 'false'} data-focused={focused ? 'true' : 'false'}
            onClick={() => onFocus?.(layer.layer_id)}>
            {cells.map((c) => (
                <g key={`${c.row}-${c.col}`}>
                    <rect
                        className="pl-fm-cell"
                        x={c.x * natural.w} y={c.y * natural.h}
                        width={c.w * natural.w} height={c.h * natural.h}
                        fillOpacity={0.08 + c.intensity * 0.62}
                        data-value={c.value}
                    />
                    {pattern ? (
                        <rect x={c.x * natural.w} y={c.y * natural.h}
                            width={c.w * natural.w} height={c.h * natural.h}
                            fill={`url(#${ns}-${pattern})`} className="pl-fm-hatch" />
                    ) : null}
                    {/* EVERY CELL BOUNDARY IS DRAWN. The grid is the measurement's resolution,
                        and a wash without it claims a precision the field does not have. */}
                    <rect
                        className="pl-fm-cellrule"
                        x={c.x * natural.w} y={c.y * natural.h}
                        width={c.w * natural.w} height={c.h * natural.h}
                        vectorEffect="non-scaling-stroke"
                        strokeDasharray={dashFor(layer)}
                    />
                </g>
            ))}
        </g>
    );
}

function PointShape({ layer, natural, dimmed, focused, onFocus }) {
    const { points } = layer.draw;
    if (!points?.length) return null;
    const r = Math.max(3, natural.w * 0.008);
    return (
        <g className="pl-fm-shape pl-fm-points" data-layer={layer.layer_id}
            data-evidence={layer.evidence} data-points={points.length}
            data-dimmed={dimmed ? 'true' : 'false'} data-focused={focused ? 'true' : 'false'}
            onClick={() => onFocus?.(layer.layer_id)}>
            {points.map(([x, y], i) => (
                <g key={i}>
                    <circle className="pl-fm-point" cx={x * natural.w} cy={y * natural.h} r={r}
                        vectorEffect="non-scaling-stroke" strokeDasharray={dashFor(layer)} />
                    {/* A CROSS THROUGH EVERY MARKER. A dot alone is told from another dot only by
                        colour, and colour is the one channel that may not carry the difference. */}
                    <path className="pl-fm-cross" vectorEffect="non-scaling-stroke"
                        d={`M${x * natural.w - r} ${y * natural.h} h${r * 2} `
                           + `M${x * natural.w} ${y * natural.h - r} v${r * 2}`} />
                </g>
            ))}
        </g>
    );
}

function PathShape({ layer, natural, ns, dimmed, focused, onFocus }) {
    const { points, arrow } = layer.draw;
    if (!points?.length) return null;
    return (
        <g className="pl-fm-shape pl-fm-path" data-layer={layer.layer_id}
            data-evidence={layer.evidence} data-arrow={arrow ? 'true' : 'false'}
            data-dimmed={dimmed ? 'true' : 'false'} data-focused={focused ? 'true' : 'false'}
            onClick={() => onFocus?.(layer.layer_id)}>
            {points.map((line, i) => (
                <path
                    key={i}
                    className="pl-fm-polyline"
                    d={line.map(([x, y], j) => `${j ? 'L' : 'M'}${x * natural.w} ${y * natural.h}`)
                        .join(' ')}
                    fill="none"
                    strokeWidth={EVIDENCE_TREATMENT[layer.evidence].strokeWidth}
                    strokeDasharray={dashFor(layer)}
                    vectorEffect="non-scaling-stroke"
                    // ONLY where the layer says so. An arrow on an undirected relation asserts an
                    // asymmetry nobody measured.
                    markerEnd={arrow ? `url(#${ns}-arrow)` : undefined}
                />
            ))}
        </g>
    );
}

const SHAPES = { rings: RingShape, cells: CellShape, points: PointShape, path: PathShape };

/**
 * The ground.
 *
 * A rule grid rather than a photograph, and the reason is on `FIXTURE_SOURCE`: these fixtures
 * carry 8×8 and 4×4 rasters describing no subject, and a photograph behind them would invite a
 * judgement about whether a mask "looks right" that the fixture cannot support.
 */
function Ground({ natural, showGrid }) {
    if (!showGrid) return <rect className="pl-fm-ground" x="0" y="0" width={natural.w} height={natural.h} />;
    const step = natural.w / 16;
    const lines = [];
    for (let x = step; x < natural.w; x += step) lines.push(['v', x]);
    for (let y = step; y < natural.h; y += step) lines.push(['h', y]);
    return (
        <g className="pl-fm-groundgroup" aria-hidden="true">
            <rect className="pl-fm-ground" x="0" y="0" width={natural.w} height={natural.h} />
            {lines.map(([dir, at], i) => (
                <line key={i} className="pl-fm-grid" vectorEffect="non-scaling-stroke"
                    x1={dir === 'v' ? at : 0} y1={dir === 'v' ? 0 : at}
                    x2={dir === 'v' ? at : natural.w} y2={dir === 'v' ? natural.h : at} />
            ))}
        </g>
    );
}

let stageSeq = 0;

export default function FormStage({
    layers = [], natural, focusId = null, onFocus = null, crop = null, showGrid = true,
    label = 'form stage', draft = null, compact = false,
}) {
    const ref = useRef(null);
    const ns = useMemo(() => { stageSeq += 1; return `pl-fm-${stageSeq}`; }, []);
    const [loaded, ,] = useNaturalSize();
    const size = natural || loaded || { w: 1600, h: 1200 };
    // Measured for the same reason every other stage in this application measures: so a pointer
    // position can be turned into a normalized coordinate without anybody re-deriving the
    // letterbox. Read by the tools in the surface above.
    useStageGeometry(ref, size);

    const drawable = layers.filter((l) => isStageLayer(l) && l.draw?.kind !== 'none');
    const refused = layers.filter((l) => l.coordinate_system === 'diagram');
    const hues = useMemo(() => {
        const map = new Map();
        drawable.forEach((l, i) => map.set(l.layer_id, HUES[i % HUES.length]));
        return map;
    }, [drawable.map((l) => l.layer_id).join('|')]); // eslint-disable-line react-hooks/exhaustive-deps

    const viewBox = crop
        ? `${crop.x * size.w} ${crop.y * size.h} ${crop.w * size.w} ${crop.h * size.h}`
        : `0 0 ${size.w} ${size.h}`;

    return (
        <div className="pl-fm-stage" ref={ref} data-compact={compact ? 'true' : 'false'}
            data-layers={drawable.length} data-focus={focusId || ''}>
            <svg
                className="pl-fm-svg"
                viewBox={viewBox}
                preserveAspectRatio="xMidYMid meet"
                role="img"
                aria-label={`${label}: ${drawable.length} drawn `
                    + `${drawable.length === 1 ? 'layer' : 'layers'}`}
            >
                <Patterns ns={ns} />
                <Ground natural={size} showGrid={showGrid} />
                {drawable.map((l) => {
                    const Shape = SHAPES[l.draw.kind];
                    if (!Shape) return null;
                    return (
                        <g key={l.layer_id} className="pl-fm-hue" data-hue={hues.get(l.layer_id)}>
                            <Shape
                                layer={l}
                                natural={size}
                                ns={ns}
                                dimmed={!!focusId && focusId !== l.layer_id}
                                focused={focusId === l.layer_id}
                                onFocus={onFocus}
                            />
                        </g>
                    );
                })}
                {draft ? (
                    <path className="pl-fm-draft" data-draft="true" fill="none"
                        vectorEffect="non-scaling-stroke"
                        d={draft.map(([x, y], i) => `${i ? 'L' : 'M'}${x * size.w} ${y * size.h}`)
                            .join(' ')} />
                ) : null}
            </svg>
            {/* A DIAGRAM LAYER THAT REACHED THE STAGE IS A BUG, and it is reported rather than
                dropped: silently skipping it would leave a person waiting for a drawing that the
                component decided not to make. */}
            {refused.length ? (
                <p className="pl-fm-refused" data-stage-refused={refused.length}>
                    {refused.length} layer{refused.length === 1 ? '' : 's'} in diagram space
                    {' '}reached the image stage and {refused.length === 1 ? 'was' : 'were'} not
                    {' '}drawn: {refused.map((l) => l.layer_id).join(', ')}. A graph node has no
                    {' '}location, and putting one at a pixel would make it look like it had one.
                </p>
            ) : null}
        </div>
    );
}
