/**
 * DEV-ONLY host for the CIRCUIT-001 P2D-B instrument spikes.
 *
 * Reachable at /lab/p2d-spike?s=konva|svg|freehand. NOT linked from any nav.
 * The whole `__spikes__` tree and this route are disposable — only the two vault
 * docs survive into P2E (report + disposition). See the report's header.
 */

import { lazy, Suspense } from 'react';
import { useSearchParams, Link } from 'react-router-dom';

const KonvaInstrumentSpike = lazy(() => import('../differential/__spikes__/KonvaInstrumentSpike'));
const SvgHandlesSpike = lazy(() => import('../differential/__spikes__/SvgHandlesSpike'));
const Spike3Panel = lazy(() => import('../differential/__spikes__/Spike3Panel'));

export default function SpikeHostPage() {
    const [params] = useSearchParams();
    const s = params.get('s') || 'konva';
    return (
        <div style={{ position: 'fixed', inset: 0, background: '#14110F' }}>
            <nav style={{ position: 'absolute', top: 8, right: 12, zIndex: 100, display: 'flex', gap: 8 }}>
                {['konva', 'svg', 'freehand'].map((k) => (
                    <Link key={k} to={`/lab/p2d-spike?s=${k}`}
                        style={{
                            padding: '4px 10px', fontSize: 12, borderRadius: 5, textDecoration: 'none',
                            background: s === k ? '#C08457' : '#241F1B', color: s === k ? '#14110F' : '#D8D2C8',
                            border: '1px solid #3A332C',
                        }}>{k}</Link>
                ))}
            </nav>
            <Suspense fallback={<div style={{ color: '#A89E90', padding: 40 }}>loading spike…</div>}>
                {s === 'konva' && <KonvaInstrumentSpike />}
                {s === 'svg' && <SvgHandlesSpike />}
                {s === 'freehand' && <Spike3Panel />}
            </Suspense>
        </div>
    );
}
