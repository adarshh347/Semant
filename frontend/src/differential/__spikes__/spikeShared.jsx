/**
 * Shared chrome, serialization panel, and image loader for the P2D-B spikes.
 *
 * Identical for Spike 1 (Konva) and Spike 2 (SVG) so the two are compared on
 * their RENDER + EDIT internals, not on incidental UI differences.
 */

/* eslint-disable react-refresh/only-export-components -- dev-only spike helper module */
import { useEffect, useState } from 'react';
import './spike.css';

export const ROLE_COLORS = {
    light_field: '#E8C07A', shadow_field: '#3B2E4A', atmosphere_field: '#8FA9BF',
    material_field: '#B08A5E', pressure_zone: '#C0576A', gaze_field: '#7FB3A8',
    negative_space: '#5A5560', threshold: '#C0845A', fold: '#8C6A4F',
    rhythm: '#9C7FB3', background_recession: '#6B7A6B', external_limit: '#7A7A7A',
};

const BRUSH_ROLES = ['light_field', 'shadow_field', 'atmosphere_field', 'fold', 'gaze_field', 'negative_space'];

/** Load an image element from a src, firing onLoad so useNaturalSize populates. */
export function useSpikeImageEl(src, onImgLoad) {
    const [el, setEl] = useState(null);
    useEffect(() => {
        const img = new window.Image();
        img.onload = () => { setEl(img); onImgLoad?.({ target: img }); };
        img.src = src;
    }, [src, onImgLoad]);
    return el;
}

export function SpikeChrome({
    title, tool, setTool, brushRole, setBrushRole, usePF, setUsePF,
    onAccept, hasSuggestion, onCommitTrace, traceOpen, layers, onToggleLayer,
    note, panel, children,
}) {
    return (
        <div className="spk-root">
            <header className="spk-head">
                <h1>{title}</h1>
                <p className="spk-sub">CIRCUIT-001 P2D-B · dev-only spike · not wired to production nav</p>
            </header>
            <div className="spk-body">
                <div className="spk-tools">
                    <div className="spk-tool-row">
                        {['select', 'brush', 'erase', 'trace'].map((t) => (
                            <button key={t} className={`spk-btn${tool === t ? ' is-on' : ''}`}
                                onClick={() => setTool(t)}>{t}</button>
                        ))}
                    </div>
                    {(tool === 'brush') && (
                        <div className="spk-tool-row spk-roles">
                            {BRUSH_ROLES.map((r) => (
                                <button key={r} className={`spk-chip${brushRole === r ? ' is-on' : ''}`}
                                    style={{ '--chip': ROLE_COLORS[r] }} onClick={() => setBrushRole(r)}>
                                    {r.replace('_field', '').replace('_', ' ')}
                                </button>
                            ))}
                        </div>
                    )}
                    <label className="spk-toggle">
                        <input type="checkbox" checked={usePF} onChange={(e) => setUsePF(e.target.checked)} />
                        taper: {usePF ? 'perfect-freehand' : 'freehandTaper'}
                    </label>
                    {traceOpen && <button className="spk-btn spk-commit" onClick={onCommitTrace}>finish trace (dbl-click)</button>}
                    {hasSuggestion && <button className="spk-btn spk-accept" onClick={onAccept}>accept suggestion →</button>}
                    <div className="spk-layers">
                        <div className="spk-layers-h">visual_layers (Groups)</div>
                        {layers.map((l) => (
                            <div key={l.id} className={`spk-layer spk-layer--${l.layer_type}`}>
                                <span className="spk-layer-name">{l.name}</span>
                                <button className={`spk-mini${l.visibility ? ' is-on' : ''}`}
                                    onClick={() => onToggleLayer(l.id, 'visibility')} title="visibility">👁</button>
                                <button className={`spk-mini${l.locked ? ' is-on' : ''}`}
                                    disabled={l.layer_type === 'recall'}
                                    onClick={() => onToggleLayer(l.id, 'locked')} title="lock">{l.locked ? '🔒' : '🔓'}</button>
                            </div>
                        ))}
                    </div>
                    {note && <p className="spk-note">{note}</p>}
                </div>
                <div className="spk-canvas-wrap">{children}</div>
                <div className="spk-panel-wrap">{panel}</div>
            </div>
        </div>
    );
}

export function SerializationPanel({ data, citable, total }) {
    // Round-trip proves the whole thing is plain JSON (throws already caught
    // upstream by assertPlainData; here it is just displayed).
    const json = JSON.stringify(data, null, 2);
    const hasRendererObj = /"attrs"|Konva|SVGElement|HTMLCanvas|"_id"/.test(json);
    return (
        <div className="spk-panel">
            <div className="spk-panel-h">
                <strong>serialized visual_marks</strong>
                <span className={`spk-badge${hasRendererObj ? ' is-bad' : ' is-ok'}`}>
                    {hasRendererObj ? 'RENDERER OBJECT LEAKED' : 'no renderer object'}
                </span>
            </div>
            <div className="spk-panel-stat">citable {citable} / {total} marks · {data.layers.length} layers</div>
            <pre className="spk-json">{json}</pre>
        </div>
    );
}
