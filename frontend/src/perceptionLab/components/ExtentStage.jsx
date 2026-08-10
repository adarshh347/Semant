import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import RegionOverlay from '../../components/RegionOverlay';
import useStageGeometry, {
    useNaturalSize, pointerToNormalized,
} from '../../differential/useStageGeometry';
import { DerivedChip, EmptyState } from './Chips';
import { decodeInstances, instanceRegions, rasterCoarseness } from '../extentView';
import { num } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the Extent stage.
 *
 * WHAT IS REUSED, AND WHY IT IS REUSED RATHER THAN REBUILT:
 *
 *   `useStageGeometry` / `useNaturalSize` / `pointerToNormalized`  the letterbox contract. A
 *       surface that reimplements `object-fit: contain` is how "the earrings land on a cheekbone"
 *       happens again, and this laboratory exists to catch that class of error rather than to
 *       reproduce it.
 *   `RegionOverlay`  the one place shapes are drawn: `viewBox` in natural pixels,
 *       `preserveAspectRatio="xMidYMid meet"`, so the overlay letterboxes exactly as the image
 *       does. Rings arrive from `extentView`, traced exactly from the mask raster.
 *
 * WHAT IS NOT REUSED, and this is deliberate: `useMaskRefine`. It fetches. Every client call in
 * this lane goes through the ONE injected client, so the refine GESTURE is reproduced here — the
 * same point/box tools, the same negative clicks, the same keys — and the dispatch goes to
 * `onRefine`, which the shell turns into an `extent.refine` proposal that passes the same four
 * gates as everything else. A refinement that skipped the resolver would be a control doing what
 * a prompt is refused.
 *
 * NATURAL SIZE. The image's decoded size is preferred; the session's DECLARED dimensions are the
 * fallback, so the overlay is correct before the image decodes. When the two disagree the stage
 * says so rather than picking one, because a declared size that does not match the pixels means
 * every normalized coordinate on this screen is landing somewhere else.
 */

const VIEWS = [
    { key: 'mask', label: 'Masks', hint: 'the traced boundary, filled' },
    { key: 'outline', label: 'Outlines', hint: 'the same boundary, unfilled — what is under it' },
    { key: 'focus', label: 'Focus', hint: 'the focused instance lit, the rest receded' },
];

const TOOLS = [
    { key: 'none', label: 'Look', hint: 'no gesture — clicking selects an instance' },
    { key: 'point', label: 'Point', kbd: 'P', hint: 'foreground/background clicks for a refinement' },
    { key: 'box', label: 'Box', kbd: 'B', hint: 'drag a refinement box' },
    { key: 'freehand', label: 'Freehand', kbd: 'F', hint: 'draw an extent by hand when nothing found it' },
];

export default function ExtentStage({ artifact, source, session, focusedInstanceId = null,
    comparisonArtifact = null, onFocusInstance, onRefine, onDraw, busy, stageRef: externalRef }) {
    const localRef = useRef(null);
    // The shell holds the ref when it needs one, so the snapshot exporter can serialize exactly
    // the element a person is looking at rather than guessing at it with a selector.
    const stageRef = externalRef || localRef;
    const [loaded, onImgLoad] = useNaturalSize();
    // MEMOIZED, and it has to be. `useStageGeometry` re-measures whenever `natural` changes
    // IDENTITY, and re-measuring sets state. A fresh object literal here therefore makes every
    // render schedule the next one — invisible in jsdom, where the stage has no size and the
    // measurement bails out, and a pinned core in a browser.
    const declared = useMemo(
        () => (session?.source
            ? { w: session.source.natural_width, h: session.source.natural_height } : null),
        [session?.source]);
    const natural = loaded || declared;
    const { content } = useStageGeometry(stageRef, natural);

    const [view, setView] = useState('mask');
    const [basis, setBasis] = useState('mask');
    const [tool, setTool] = useState('none');
    const [negative, setNegative] = useState(false);
    const [points, setPoints] = useState([]);
    const [box, setBox] = useState(null);
    const [draftBox, setDraftBox] = useState(null);
    const [stroke, setStroke] = useState([]);
    const [showComparison, setShowComparison] = useState(true);
    const drawing = useRef(false);

    const instances = useMemo(() => decodeInstances(artifact), [artifact]);
    const regions = useMemo(
        () => instanceRegions(instances, { basis }), [instances, basis]);
    const comparison = useMemo(
        () => decodeInstances(comparisonArtifact), [comparisonArtifact]);
    const comparisonRegions = useMemo(
        () => instanceRegions(comparison, { basis }), [comparison, basis]);
    const coarseness = useMemo(
        () => rasterCoarseness(instances, natural), [instances, natural]);

    const clear = useCallback(() => {
        setPoints([]); setBox(null); setDraftBox(null); setStroke([]);
    }, []);

    useEffect(() => {
        const onKey = (e) => {
            if (e.target instanceof HTMLInputElement
                || e.target instanceof HTMLTextAreaElement) return;
            const k = e.key.toLowerCase();
            if (k === 'p') setTool('point');
            else if (k === 'b') setTool('box');
            else if (k === 'f') setTool('freehand');
            else if (k === 'n') setNegative((v) => !v);
            else if (e.key === 'Escape') { clear(); setTool('none'); }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [clear]);

    const toNorm = (e) => pointerToNormalized(e, stageRef.current, content, { clamp: true });

    const onPointerDown = (e) => {
        if (!content || tool === 'none') return;
        e.preventDefault();
        const p = toNorm(e);
        if (!p) return;
        if (tool === 'box') {
            drawing.current = true;
            setDraftBox({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
        } else if (tool === 'freehand') {
            drawing.current = true;
            setStroke([[p.x, p.y]]);
        }
    };
    const onPointerMove = (e) => {
        if (!drawing.current) return;
        const p = toNorm(e);
        if (!p) return;
        if (tool === 'box') setDraftBox((b) => (b ? { ...b, x1: p.x, y1: p.y } : b));
        else if (tool === 'freehand') setStroke((s) => [...s, [p.x, p.y]]);
    };
    const onPointerUp = () => {
        if (!drawing.current) return;
        drawing.current = false;
        if (tool === 'box' && draftBox) {
            const b = draftBox;
            setDraftBox(null);
            if (Math.abs(b.x1 - b.x0) > 0.012 && Math.abs(b.y1 - b.y0) > 0.012) {
                setBox({ x: Math.min(b.x0, b.x1), y: Math.min(b.y0, b.y1),
                    w: Math.abs(b.x1 - b.x0), h: Math.abs(b.y1 - b.y0) });
            }
        }
    };
    /**
     * A point is a PAIR.
     *
     * `point_list` is `[[x, y], …]` in the contract — there is no per-point label, because in this
     * grammar polarity belongs to the whole refinement (`mode: add | subtract | replace`) and not
     * to each click. Collecting `[x, y, 0]` triples would have been quietly rejected by
     * `resolveParameters` as "not a point_list", so the surface would have been offering a
     * distinction it could not carry. The two propose buttons carry it instead.
     */
    const onClick = (e) => {
        if (tool !== 'point' || !content) return;
        const p = toNorm(e);
        if (!p) return;
        if (negative || e.shiftKey) setNegative(true);
        setPoints((prev) => [...prev, [p.x, p.y]]);
    };

    if (!artifact) {
        return (
            <section className="pl-panel" aria-label="Extent stage">
                <div className="pl-panel-head"><h2 className="pl-panel-title">Stage</h2></div>
                <EmptyState title="Nothing is drawn yet"
                    hint="Run an extent operation, or draw one by hand. A stage with no
                        measurement on it shows the image and says so." />
                <div className="pl-stage" ref={stageRef}>
                    <img src={source?.photo_url} alt="" onLoad={onImgLoad} draggable={false} />
                </div>
            </section>
        );
    }

    const lit = focusedInstanceId ? new Set([focusedInstanceId]) : null;
    // A drawn extent must never acquire the look of a segmented one, so the artifact's own basis
    // outranks the toggle: `manual` is `manual` whatever the person is currently looking at.
    const drawnBasis = artifact.measurement.epistemic_basis === 'manual' ? 'manual' : basis;
    const maskRegions = regions.filter((r) => r.basis !== 'box' || drawnBasis !== 'mask');
    const boxRegions = drawnBasis === 'mask' ? regions.filter((r) => r.basis === 'box') : [];
    const promptShape = {
        box: draftBox || (box ? { x0: box.x, y0: box.y, x1: box.x + box.w, y1: box.y + box.h }
            : null),
        // The marker shows the polarity the whole gesture currently carries, so a person can see
        // which of the two propose buttons their clicks are heading for.
        points: points.map(([x, y]) => ({ x, y, label: negative ? 0 : 1 })),
    };

    return (
        <section className="pl-panel" aria-label="Extent stage" data-extent-stage>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Stage</h2>
                <span className="pl-chiprow">
                    <DerivedChip why="the boundary drawn here is traced from the measured mask
                        raster in this browser. The measurement is the RLE; this is a picture
                        of it." />
                    <span className="pl-chip" data-drawn-basis={basis}>
                        drawn on the {basis} basis
                    </span>
                </span>
            </div>

            <div className="pl-modes" role="group" aria-label="Stage view">
                <div className="pl-modegroup">
                    <span className="pl-modegroup-label" id="pl-view-label">View</span>
                    <span className="pl-segmented" role="group" aria-labelledby="pl-view-label">
                        {VIEWS.map((v) => (
                            <button key={v.key} type="button" className="pl-btn"
                                data-view-mode={v.key} aria-pressed={view === v.key}
                                title={v.hint} onClick={() => setView(v.key)}>
                                {v.label}
                            </button>
                        ))}
                    </span>
                </div>
                <div className="pl-modegroup">
                    <span className="pl-modegroup-label" id="pl-basis-label">Basis</span>
                    <span className="pl-segmented" role="group" aria-labelledby="pl-basis-label">
                        <button type="button" className="pl-btn" data-basis-mode="mask"
                            aria-pressed={basis === 'mask'}
                            title="the exact traced boundary" onClick={() => setBasis('mask')}>
                            Mask
                        </button>
                        <button type="button" className="pl-btn" data-basis-mode="box"
                            aria-pressed={basis === 'box'}
                            title="the same instances as bounding boxes — what a box-basis
                                relation is actually measured on"
                            onClick={() => setBasis('box')}>
                            Box
                        </button>
                    </span>
                </div>
                <div className="pl-modegroup">
                    <span className="pl-modegroup-label" id="pl-tool-label">Tool</span>
                    <span className="pl-segmented" role="group" aria-labelledby="pl-tool-label">
                        {TOOLS.map((t) => (
                            <button key={t.key} type="button" className="pl-btn"
                                data-tool={t.key} aria-pressed={tool === t.key}
                                title={t.hint} onClick={() => { setTool(t.key); }}>
                                {t.label}{t.kbd ? <kbd> {t.kbd}</kbd> : null}
                            </button>
                        ))}
                    </span>
                </div>
                {comparisonArtifact ? (
                    <div className="pl-modegroup">
                        <span className="pl-modegroup-label">Comparison</span>
                        <button type="button" className="pl-btn" data-show-comparison
                            aria-pressed={showComparison}
                            onClick={() => setShowComparison((v) => !v)}>
                            {showComparison ? 'A over B' : 'A only'}
                        </button>
                    </div>
                ) : null}
            </div>

            {basis === 'box' ? (
                <p className="pl-panel-sub" data-box-basis-note>
                    These are bounding boxes of the same masks. Every relation measured on this
                    basis is <strong>interpretive however confident the number</strong>, because
                    the rectangle claims area the mask never did.
                </p>
            ) : null}

            <div className={`pl-stage tool-${tool}`} ref={stageRef} data-view={view}
                onPointerDown={onPointerDown} onPointerMove={onPointerMove}
                onPointerUp={onPointerUp} onClick={onClick}
                onDragStart={(e) => e.preventDefault()}>
                <img src={source?.photo_url} alt="" onLoad={onImgLoad} draggable={false} />
                {natural ? (
                    <>
                        {comparisonArtifact && showComparison ? (
                            <RegionOverlay
                                className="pl-svg pl-svg--passive"
                                natural={natural}
                                regions={comparisonRegions.map((r) => ({
                                    ...r, id: `cmp_${r.id}` }))}
                                viewMap="outline"
                                interactive={false} />
                        ) : null}
                        {/*
                          * ONE LAYER PER BASIS, and it is not a styling preference.
                          *
                          * `RegionOverlay` styles shapes through `rs-shape--${viewMap}`, which is
                          * per-overlay. A set that mixes exact masks with box-only instances
                          * therefore has to be drawn as two layers, or the dashed box-basis
                          * treatment would apply to everything or to nothing — and a box drawn
                          * like a mask is precisely the substitution the epistemics forbid.
                          * `viewMap` carries the BASIS; the view mode rides `data-view` on the
                          * stage, so the two never have to share one string.
                          */}
                        {maskRegions.length ? (
                            <RegionOverlay
                                className="pl-svg"
                                natural={natural}
                                regions={maskRegions}
                                viewMap={drawnBasis}
                                focusId={focusedInstanceId}
                                litIds={lit}
                                onSelect={(id) => onFocusInstance?.(id)}
                                prompt={promptShape}
                                interactive={tool === 'none'} />
                        ) : null}
                        {boxRegions.length ? (
                            <RegionOverlay
                                className="pl-svg"
                                natural={natural}
                                regions={boxRegions}
                                viewMap="box"
                                focusId={focusedInstanceId}
                                litIds={lit}
                                onSelect={(id) => onFocusInstance?.(id)}
                                interactive={tool === 'none'} />
                        ) : null}
                        {stroke.length > 1 ? (
                            <svg className="pl-svg pl-svg--passive"
                                viewBox={`0 0 ${natural.w} ${natural.h}`}
                                preserveAspectRatio="xMidYMid meet" aria-hidden="true">
                                <polyline className="pl-freehand" data-freehand
                                    points={stroke.map(([x, y]) =>
                                        `${x * natural.w},${y * natural.h}`).join(' ')} />
                            </svg>
                        ) : null}
                    </>
                ) : null}
            </div>

            <StageNote natural={natural} loaded={loaded} declared={declared}
                coarseness={coarseness} regions={regions} />

            {tool !== 'none' ? (
                <div className="pl-field" data-gesture>
                    <span className="pl-label">
                        {tool === 'freehand' ? 'Drawn by hand' : 'Refinement evidence'}
                    </span>
                    <p className="pl-panel-sub" data-gesture-state>
                        {tool === 'point'
                            ? `${points.length} point${points.length === 1 ? '' : 's'} · `
                                + `${negative ? 'subtracting' : 'adding'} — polarity belongs to `
                                + 'the whole refinement here, not to each click'
                            : tool === 'box'
                                ? (box ? `a box at ${num(box.x)}, ${num(box.y)}`
                                    : 'drag a box on the image')
                                : `${stroke.length} points traced`}
                        {' · '}
                        nothing has been proposed yet. A gesture is evidence, and it becomes a
                        plan only when you send it — through the same resolver as everything else.
                    </p>
                    <div className="pl-btnrow">
                        {tool === 'point' ? (
                            <button type="button" className="pl-btn" data-negative
                                aria-pressed={negative}
                                title="which of the two proposals these clicks are evidence for.
                                    The contract carries polarity on the refinement, not on the
                                    point, so this is a mode and not a label."
                                onClick={() => setNegative((v) => !v)}>
                                − Subtracting<kbd> N</kbd>
                            </button>
                        ) : null}
                        {tool === 'freehand' ? (
                            <button type="button" className="pl-btn pl-btn--primary"
                                data-action="propose-draw"
                                disabled={stroke.length < 3 || !!busy}
                                onClick={() => { onDraw?.(stroke); clear(); }}>
                                Propose a drawn extent
                            </button>
                        ) : (
                            <>
                                <button type="button" className="pl-btn pl-btn--primary"
                                    data-action="propose-refine-add"
                                    disabled={(!points.length && !box) || !focusedInstanceId
                                        || !!busy}
                                    onClick={() => {
                                        onRefine?.('add', { points, box, instanceId:
                                            focusedInstanceId });
                                        clear();
                                    }}>
                                    Propose: add to {focusedInstanceId || 'an instance'}
                                </button>
                                <button type="button" className="pl-btn"
                                    data-action="propose-refine-subtract"
                                    disabled={(!points.length && !box) || !focusedInstanceId
                                        || !!busy}
                                    onClick={() => {
                                        onRefine?.('subtract', { points, box, instanceId:
                                            focusedInstanceId });
                                        clear();
                                    }}>
                                    Propose: subtract
                                </button>
                            </>
                        )}
                        <button type="button" className="pl-btn pl-btn--quiet" data-action="clear"
                            onClick={clear}>Clear<kbd> Esc</kbd></button>
                    </div>
                    {!focusedInstanceId && tool !== 'freehand' ? (
                        <p className="pl-panel-sub" data-no-focus>
                            A refinement changes one extent, so one has to be focused first.
                            Choose an instance in the inspector or click it on the stage — the
                            laboratory will not pick the first one for you.
                        </p>
                    ) : null}
                </div>
            ) : null}
        </section>
    );
}

/** What the drawing does and does not guarantee, said under the drawing. */
function StageNote({ natural, loaded, declared, coarseness, regions }) {
    const disagree = loaded && declared && (loaded.w !== declared.w || loaded.h !== declared.h);
    const unavailable = regions.filter((r) => r.unavailable);
    return (
        <div className="pl-stage-legend" data-stage-note>
            <span className="pl-swatch pl-swatch--figure" aria-hidden="true" />
            <span>
                {natural
                    ? `drawn in ${natural.w}×${natural.h} natural pixels`
                    : 'the image has not reported a size yet, so nothing is drawn'}
                {loaded ? '' : ' (declared by the session; the image has not decoded)'}
            </span>
            {disagree ? (
                <span className="pl-dangling" data-size-disagreement>
                    THE DECLARED SIZE IS NOT THE IMAGE SIZE ({declared.w}×{declared.h} declared,
                    {' '}{loaded.w}×{loaded.h} decoded). Every normalized coordinate on this stage
                    is landing somewhere other than where it was measured.
                </span>
            ) : null}
            {coarseness ? (
                <span data-raster-coarseness={coarseness.coarse ? 'coarse' : 'fine'}
                    title="the grid the measurement was taken on, in image pixels per mask cell">
                    mask raster {coarseness.raster.h}×{coarseness.raster.w} ·{' '}
                    {num(coarseness.cell_px.x, 1)}×{num(coarseness.cell_px.y, 1)}px per cell
                    {coarseness.coarse
                        ? ' — the edge is drawn crisply and was not measured crisply'
                        : ''}
                </span>
            ) : null}
            {unavailable.length ? (
                <span className="pl-dangling" data-undrawable={unavailable.length}>
                    {unavailable.length} instance{unavailable.length === 1 ? '' : 's'} could not be
                    drawn: {unavailable[0].unavailable}
                </span>
            ) : null}
        </div>
    );
}
