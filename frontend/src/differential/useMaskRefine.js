import { useCallback, useEffect, useRef, useState } from 'react';
import { API_URL } from '../config/api';

/**
 * useMaskRefine (VISION-B5) — the shared exact-mask refinement loop.
 *
 * Owns the prompt state + the B4 endpoints so both the lab harness (RefineSurface) and
 * the product surface (DifferentialWorkspace's Refine tool) drive the same logic. Coords
 * are normalized [0,1] (the stage-geometry contract); the caller converts pointer →
 * normalized and feeds `addPoint` / `setBoxPrompt`. Preview never persists; `confirm`
 * saves a new geometry revision and returns `{region, post}`; `cancel`/`clear` change
 * nothing on the server. `release` frees the SAM session (call when refinement ends).
 *
 * `baseRegion` (optional) makes it an in-place upgrade of that region's mask identity
 * (Select → Refine); absent, it proposes a fresh region.
 */
export default function useMaskRefine(postId, baseRegion) {
  const [points, setPoints] = useState([]);      // {x, y, label} normalized
  const [box, setBox] = useState(null);          // {x0, y0, x1, y1} normalized
  const [proposal, setProposal] = useState(null);
  const [status, setStatus] = useState('idle');  // idle|loading|ok|empty|error|confirmed
  const [error, setError] = useState('');
  const reqSeq = useRef(0);
  const baseId = baseRegion?.id || null;
  const baseRev = baseRegion?.geometry_rev || 0;

  const body = useCallback((pts, bx) => {
    const b = {};
    if (pts && pts.length) { b.points = pts.map((p) => [p.x, p.y]); b.labels = pts.map((p) => p.label); }
    if (bx) b.box = [Math.min(bx.x0, bx.x1), Math.min(bx.y0, bx.y1), Math.max(bx.x0, bx.x1), Math.max(bx.y0, bx.y1)];
    if (baseId) { b.base_id = baseId; b.base_geometry_rev = baseRev; }
    return b;
  }, [baseId, baseRev]);

  const runPreview = useCallback(async (pts, bx) => {
    if ((!pts || !pts.length) && !bx) { setProposal(null); setStatus('idle'); return; }
    const seq = ++reqSeq.current;
    setStatus('loading'); setError('');
    try {
      const res = await fetch(`${API_URL}/api/v1/posts/${postId}/refine-region/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body(pts, bx)),
      });
      if (!res.ok) throw new Error(res.status === 503 ? 'refiner unavailable' : `refiner ${res.status}`);
      const data = await res.json();
      if (seq !== reqSeq.current) return;                 // a newer prompt won
      const r = data.region;
      const weak = !r || !(r.polygons && r.polygons.length) || (r.confidence != null && r.confidence < 0.2);
      setProposal(r || null); setStatus(weak ? 'empty' : 'ok');
    } catch (e) {
      if (seq !== reqSeq.current) return;
      setError(String(e.message || e)); setStatus('error'); setProposal(null);
    }
  }, [postId, body]);

  useEffect(() => {
    const t = setTimeout(() => runPreview(points, box), 110);
    return () => clearTimeout(t);
  }, [points, box, runPreview]);

  const addPoint = useCallback((x, y, label = 1) => { setBox(null); setPoints((p) => [...p, { x, y, label }]); }, []);
  const setBoxPrompt = useCallback((b) => { setPoints([]); setBox(b); }, []);
  const clear = useCallback(() => {
    reqSeq.current++; setPoints([]); setBox(null); setProposal(null); setStatus('idle'); setError('');
  }, []);

  const confirm = useCallback(async () => {
    if (status !== 'ok' || !proposal) return null;
    setStatus('loading');
    try {
      const res = await fetch(`${API_URL}/api/v1/posts/${postId}/refine-region/confirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body(points, box)),
      });
      if (!res.ok) throw new Error(`confirm ${res.status}`);
      const data = await res.json();
      setPoints([]); setBox(null); setProposal(null); setStatus('confirmed');
      return data;                                        // {region, post}
    } catch (e) { setError(String(e.message || e)); setStatus('error'); return null; }
  }, [status, proposal, points, box, postId, body]);

  const release = useCallback(async () => {
    try { await fetch(`${API_URL}/api/v1/posts/refine-region/unload`, { method: 'POST' }); } catch { /* best effort */ }
  }, []);

  return {
    points, box, proposal, status, error,
    hasPrompt: points.length > 0 || !!box,
    addPoint, setBoxPrompt, clear, confirm, release,
  };
}
