/**
 * Spike 3 visual side-by-side — perfect-freehand vs freehandTaper on the SAME
 * heavy stroke, so the taper-quality difference the numbers describe can be seen.
 * DEV-ONLY.
 */

import { useMemo, useState } from 'react';
import { taperedRibbon } from '../freehandTaper';
import { strokeViaPerfectFreehand, polygonToPath, compareTaper } from './freehandCompare';
import { synthesizeHeavyStroke } from './spikeFixture';
import './spike.css';

const NAT = { w: 900, h: 600 };
const SHORT = [[0.18, 0.42, 0.3], [0.28, 0.30, 0.7], [0.42, 0.26, 1.0], [0.58, 0.30, 0.9], [0.72, 0.44, 0.6], [0.82, 0.60, 0.3]];

function Ribbon({ points, title, sub }) {
    const px = points.map(([x, y, p]) => [x * NAT.w, y * NAT.h, p]);
    const ft = taperedRibbon(px, { maxWidth: 0.02 * NAT.w });
    const pf = polygonToPath(strokeViaPerfectFreehand(px, { size: 0.02 * NAT.w }));
    return (
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
                <div style={{ fontSize: 11, color: '#A89E90', marginBottom: 4 }}>{title} · <b>freehandTaper</b> · {sub}</div>
                <svg width={340} height={227} viewBox={`0 0 ${NAT.w} ${NAT.h}`} style={{ background: '#1A1613', borderRadius: 6 }}>
                    <path d={ft} fill="#E8C07A" fillOpacity={0.85} />
                </svg>
            </div>
            <div>
                <div style={{ fontSize: 11, color: '#A89E90', marginBottom: 4 }}>{title} · <b>perfect-freehand</b> · {sub}</div>
                <svg width={340} height={227} viewBox={`0 0 ${NAT.w} ${NAT.h}`} style={{ background: '#1A1613', borderRadius: 6 }}>
                    <path d={pf} fill="#7FB3A8" fillOpacity={0.85} />
                </svg>
            </div>
        </div>
    );
}

export default function Spike3Panel() {
    const heavy = useMemo(() => synthesizeHeavyStroke(), []);
    const [report] = useState(() => ({
        heavy: compareTaper(heavy.points, NAT, { runs: 30 }),
        short: compareTaper(SHORT, NAT, { runs: 30 }),
    }));
    const row = (label, r) => (
        <tr>
            <td>{label}</td>
            <td>{r.input.points}</td>
            <td>{r.freehandTaper.vertices}</td>
            <td>{r.perfectFreehand.vertices}</td>
            <td>{r.freehandTaper.pathChars}</td>
            <td>{r.perfectFreehand.pathChars}</td>
            <td>{r.freehandTaper.timing.median.toFixed(3)}</td>
            <td>{r.perfectFreehand.timing.median.toFixed(3)}</td>
            <td>{r.freehandTaper.pressureSensitivityPx.toFixed(1)}</td>
            <td>{r.perfectFreehand.pressureSensitivityPx.toFixed(1)}</td>
        </tr>
    );
    return (
        <div className="spk-root" style={{ overflow: 'auto' }}>
            <header className="spk-head">
                <h1>Spike 3 · perfect-freehand vs freehandTaper</h1>
                <p className="spk-sub">CIRCUIT-001 P2D-B · pure points-in / polygon-out · zero ontology risk</p>
            </header>
            <div style={{ padding: 20 }}>
                <Ribbon points={heavy.points} title="heavy (1194 pts, real corpus max)" sub="tapered ribbon" />
                <Ribbon points={SHORT} title="short (6 pts)" sub="tapered ribbon" />
                <table className="spk-json" style={{ borderCollapse: 'collapse', width: '100%', maxWidth: 900 }}>
                    <thead>
                        <tr style={{ textAlign: 'left', color: '#C08457' }}>
                            <th>stroke</th><th>in-pts</th><th>FT-vtx</th><th>PF-vtx</th><th>FT-chars</th><th>PF-chars</th>
                            <th>FT-ms</th><th>PF-ms</th><th>FT-press</th><th>PF-press</th>
                        </tr>
                    </thead>
                    <tbody>
                        {row('heavy 1194', report.heavy)}
                        {row('short 6', report.short)}
                    </tbody>
                </table>
                <p className="spk-note" style={{ maxWidth: 900, marginTop: 16 }}>
                    press = mean px the outline shifts when real pressure is flattened to constant — higher = more
                    pressure-responsive. FT = freehandTaper (vendored, current). PF = perfect-freehand (candidate).
                    Storage is UNAFFECTED either way: both store input points and regenerate the polygon at render,
                    so PF's larger vertex count is a render/raster cost, not a stored-record cost.
                </p>
            </div>
        </div>
    );
}
