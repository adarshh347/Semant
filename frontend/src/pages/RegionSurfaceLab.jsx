import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { API_URL } from '../config/api';
import RegionSurface from '../components/RegionSurface';
import './RegionSurfaceLab.css';

/**
 * Dev harness for RegionSurface (Darshan Track D · Phase 1).
 *
 * The component's whole responsiveness claim is that it reacts to the width of the PANE
 * it sits in, not the browser window. A harness that resized the window would prove
 * nothing, so this one holds the window still and squeezes the container instead —
 * exactly the situation a resizable split creates.
 *
 *   /lab/region-surface/:postId            → default pane width
 *   ?w=wide | default | narrow | cramped   → pane width preset
 *   ?n=40                                  → synthesize N regions (the many-parts case)
 *
 * Not linked from the app. It exists so Phase 1 can be verified before Phase 4 mounts
 * the component in the real Visual pane.
 */

const WIDTHS = {
    wide: 1100,
    default: 720,
    narrow: 430,
    cramped: 320,
};

/** Deterministic synthetic regions — the 30-40 split case Adarsh is designing for. */
function synthesize(base, n) {
    const cats = ['garment', 'garment-detail', 'accessory', 'skin', 'hair', 'object'];
    const out = [...base];
    for (let i = out.length; i < n; i++) {
        const col = i % 6, row = Math.floor(i / 6) % 6;
        const x = 0.08 + col * 0.14, y = 0.06 + row * 0.145;
        const w = 0.10 + ((i * 7) % 5) * 0.012, h = 0.09 + ((i * 3) % 5) * 0.012;
        // a real polygon, not a rectangle — the surface must draw outlines by default
        const poly = [
            [x, y + h * 0.3], [x + w * 0.35, y], [x + w, y + h * 0.22],
            [x + w * 0.82, y + h], [x + w * 0.2, y + h * 0.9],
        ];
        out.push({
            id: `synth_${i}`, actor: 'auto', detector: 'segformer_clothes',
            label: `part ${i + 1}`, category: cats[i % cats.length], material: '',
            description: '', part: null, attributes: [],
            box: { x, y, w, h }, polygon: poly, confidence: 0.7,
            depth: i % 3 === 0 ? 0 : 1,
            parent_id: i % 3 === 0 ? null : `synth_${i - (i % 3)}`,
            prioritised: false, weight: 0, user_note: '',
        });
    }
    return out;
}

export default function RegionSurfaceLab() {
    const { postId } = useParams();
    const [params] = useSearchParams();
    const preset = params.get('w') || 'default';
    const n = parseInt(params.get('n') || '0', 10);

    const [post, setPost] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        fetch(`${API_URL}/api/v1/posts/${postId}`)
            .then(r => r.json())
            .then(p => {
                const regions = n ? synthesize(p.region_annotations || [], n)
                    : (p.region_annotations || []);
                setPost({ ...p, region_annotations: regions });
            })
            .catch(() => setError('Could not load the post.'));
    }, [postId, n]);

    if (error) return <p className="lab-msg">{error}</p>;
    if (!post) return <p className="lab-msg">Loading…</p>;

    return (
        <div className="lab">
            <header className="lab-bar">
                <span className="lab-kicker">RegionSurface · Phase 1 harness</span>
                <nav className="lab-widths">
                    {Object.entries(WIDTHS).map(([key, px]) => (
                        <a key={key} className={`lab-w${preset === key ? ' on' : ''}`}
                            href={`?w=${key}${n ? `&n=${n}` : ''}`}>{key} · {px}px</a>
                    ))}
                    <a className={`lab-w${n ? ' on' : ''}`}
                        href={`?w=${preset}${n ? '' : '&n=40'}`}>{n ? 'real regions' : '40 regions'}</a>
                </nav>
                <span className="lab-meta">
                    pane {WIDTHS[preset]}px · {post.region_annotations.length} regions
                </span>
            </header>

            {/* The pane. Its width is fixed; the window is not resized. */}
            <div className="lab-pane" style={{ width: WIDTHS[preset] }}>
                <RegionSurface
                    post={post}
                    aletheia={post.local_context?.aletheia || null}
                    onPostChange={(p) => setPost(prev => ({ ...p, region_annotations: prev.region_annotations }))}
                />
            </div>
        </div>
    );
}
