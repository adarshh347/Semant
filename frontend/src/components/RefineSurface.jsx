import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_URL } from '../config/api';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from '../differential/useStageGeometry';
import { ringsToPath } from '../lib/maskGeometry';
import './RefineSurface.css';

/**
 * RefineSurface (VISION-BUILD-001 B4) — the interactive exact-mask refinement loop.
 *
 * Point / box prompts → a live SAM 2.1 preview mask (proposed, not saved) → Confirm
 * persists a new geometry revision; Cancel leaves evidence untouched. It rides the
 * shared stage-geometry contract (viewBox = natural, `xMidYMid meet` = object-fit
 * contain), so the mask stays registered to the image at any size or zoom.
 *
 * Critical: while a point/box gesture is active the image must NOT pan or drag. Every
 * pointer event is preventDefault'd, the <img> is undraggable, and the stage disables
 * selection/native drag — the DIFF-UX-GATE-001 lesson, applied here by construction.
 */

const reducedMotion = () =>
  typeof window !== 'undefined' && !!window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function RefineSurface({ post, postId, onConfirmed }) {
  const id = postId || post?._id || post?.id;
  const stageRef = useRef(null);
  const [natural, onImgLoad] = useNaturalSize();
  const { content } = useStageGeometry(stageRef, natural);

  const [tool, setTool] = useState('point');       // 'point' | 'box'
  const [negative, setNegative] = useState(false);
  const [points, setPoints] = useState([]);        // [{x,y,label}] normalized
  const [box, setBox] = useState(null);            // {x0,y0,x1,y1} normalized
  const [draftBox, setDraftBox] = useState(null);
  const [proposal, setProposal] = useState(null);  // proposed region
  const [status, setStatus] = useState('idle');    // idle|loading|ok|empty|error|confirmed
  const [error, setError] = useState('');
  const [showBase, setShowBase] = useState(true);
  const drawing = useRef(false);
  const reqSeq = useRef(0);
  const reduced = reducedMotion();

  const baseRegion = useMemo(
    () => (post?.region_annotations || []).find(r => r.mask_rle || (r.polygons && r.polygons.length)) || null,
    [post]);

  const nb = natural || { w: 1, h: 1 };

  // ── preview: call the refiner whenever the prompt changes (debounced) ──────
  const runPreview = useCallback(async (pts, bx) => {
    if ((!pts || !pts.length) && !bx) { setProposal(null); setStatus('idle'); return; }
    const seq = ++reqSeq.current;
    setStatus('loading'); setError('');
    try {
      const body = {};
      if (pts && pts.length) { body.points = pts.map(p => [p.x, p.y]); body.labels = pts.map(p => p.label); }
      if (bx) body.box = [Math.min(bx.x0, bx.x1), Math.min(bx.y0, bx.y1),
                          Math.max(bx.x0, bx.x1), Math.max(bx.y0, bx.y1)];
      if (baseRegion) { body.base_id = baseRegion.id; body.base_geometry_rev = baseRegion.geometry_rev || 0; }
      const res = await fetch(`${API_URL}/api/v1/posts/${id}/refine-region/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(res.status === 503 ? 'refiner unavailable' : `refiner ${res.status}`);
      const data = await res.json();
      if (seq !== reqSeq.current) return;                    // a newer prompt won
      const r = data.region;
      const weak = !r || !(r.polygons && r.polygons.length) || (r.confidence != null && r.confidence < 0.2);
      setProposal(r || null);
      setStatus(weak ? 'empty' : 'ok');
    } catch (e) {
      if (seq !== reqSeq.current) return;
      setError(String(e.message || e)); setStatus('error'); setProposal(null);
    }
  }, [id, baseRegion]);

  useEffect(() => {
    const t = setTimeout(() => runPreview(points, box), 110);
    return () => clearTimeout(t);
  }, [points, box, runPreview]);

  // ── pointer handling — prevents stage pan / image drag while refining ──────
  const toNorm = (e) => pointerToNormalized(e, stageRef.current, content, { clamp: true });

  const onPointerDown = (e) => {
    if (!content) return;
    e.preventDefault();                                       // stop native drag/pan
    try { stageRef.current.setPointerCapture(e.pointerId); } catch { /* */ }
    if (tool === 'box') {
      const p = toNorm(e); if (!p) return;
      drawing.current = true;
      setDraftBox({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
    }
  };
  const onPointerMove = (e) => {
    if (tool === 'box' && drawing.current) {
      e.preventDefault();
      const p = toNorm(e); if (!p) return;
      setDraftBox((b) => (b ? { ...b, x1: p.x, y1: p.y } : b));
    }
  };
  const onPointerUp = (e) => {
    if (tool === 'box' && drawing.current) {
      e.preventDefault();
      drawing.current = false;
      const b = draftBox; setDraftBox(null);
      if (b && Math.abs(b.x1 - b.x0) > 0.012 && Math.abs(b.y1 - b.y0) > 0.012) {
        setPoints([]); setBox(b);
      }
    }
  };
  const onClick = (e) => {
    if (tool !== 'point' || !content) return;
    e.preventDefault();
    const p = toNorm(e); if (!p) return;
    const label = (negative || e.shiftKey || e.altKey) ? 0 : 1;
    setBox(null);
    setPoints((pts) => [...pts, { x: p.x, y: p.y, label }]);
  };

  const clearPrompt = useCallback(() => {
    setPoints([]); setBox(null); setDraftBox(null); setProposal(null);
    setStatus('idle'); setError('');
  }, []);

  const confirm = useCallback(async () => {
    if (status !== 'ok' || !proposal) return;
    setStatus('loading');
    try {
      const body = {};
      if (points.length) { body.points = points.map(p => [p.x, p.y]); body.labels = points.map(p => p.label); }
      if (box) body.box = [Math.min(box.x0, box.x1), Math.min(box.y0, box.y1),
                           Math.max(box.x0, box.x1), Math.max(box.y0, box.y1)];
      if (baseRegion) { body.base_id = baseRegion.id; body.base_geometry_rev = baseRegion.geometry_rev || 0; }
      const res = await fetch(`${API_URL}/api/v1/posts/${id}/refine-region/confirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`confirm ${res.status}`);
      const data = await res.json();
      clearPrompt(); setStatus('confirmed');
      onConfirmed?.(data.region, data.post);
    } catch (e) { setError(String(e.message || e)); setStatus('error'); }
  }, [status, proposal, points, box, baseRegion, id, clearPrompt, onConfirmed]);

  const cancel = useCallback(() => { clearPrompt(); onConfirmed?.(null); }, [clearPrompt, onConfirmed]);

  // keyboard: Esc clear · Enter confirm · P point · B box · N negative
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') clearPrompt();
      else if (e.key === 'Enter') confirm();
      else if (e.key === 'b' || e.key === 'B') setTool('box');
      else if (e.key === 'p' || e.key === 'P') setTool('point');
      else if (e.key === 'n' || e.key === 'N') setNegative((v) => !v);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [clearPrompt, confirm]);

  const b = draftBox || box;
  const mk = Math.max(4, nb.w * 0.011);

  return (
    <div className="refine">
      <div className="refine-toolbar" role="toolbar" aria-label="Refinement tools">
        <div className="refine-tools">
          <button className={`rf-btn ${tool === 'point' ? 'is-on' : ''}`} aria-pressed={tool === 'point'}
                  onClick={() => setTool('point')}>Point <kbd>P</kbd></button>
          <button className={`rf-btn ${tool === 'box' ? 'is-on' : ''}`} aria-pressed={tool === 'box'}
                  onClick={() => setTool('box')}>Box <kbd>B</kbd></button>
          <button className={`rf-btn ${negative ? 'is-neg' : ''}`} aria-pressed={negative}
                  title="Negative clicks subtract from the mask"
                  onClick={() => setNegative((v) => !v)}>− Negative <kbd>N</kbd></button>
          {baseRegion && (
            <button className={`rf-btn ${showBase ? 'is-on' : ''}`} aria-pressed={showBase}
                    onClick={() => setShowBase((v) => !v)}>Before/after</button>
          )}
        </div>
        <div className="refine-status" aria-live="polite">
          {status === 'loading' && (<><span className="rf-spin" /> Refining…</>)}
          {status === 'ok' && `Proposed · ${Math.round((proposal.confidence || 0) * 100)}% · rev ${proposal.geometry_rev}`}
          {status === 'empty' && 'No confident mask yet — add a point or drag a box'}
          {status === 'error' && <span className="rf-err">Refiner error: {error}</span>}
          {status === 'confirmed' && <span className="rf-ok">Saved ✓</span>}
          {status === 'idle' && 'Click the subject, or drag a box'}
        </div>
        <div className="refine-actions">
          <button className="rf-btn" onClick={clearPrompt}>Clear <kbd>Esc</kbd></button>
          <button className="rf-btn rf-cancel" onClick={cancel}>Cancel</button>
          <button className="rf-btn rf-confirm" disabled={status !== 'ok'} onClick={confirm}>Confirm <kbd>⏎</kbd></button>
        </div>
      </div>

      <div className={`refine-stage tool-${tool}`} ref={stageRef}
           onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
           onClick={onClick} onDragStart={(e) => e.preventDefault()}>
        <img className="refine-img" src={post?.photo_url} alt="" draggable={false} onLoad={onImgLoad} />
        {natural && (
          <svg className="refine-svg" viewBox={`0 0 ${nb.w} ${nb.h}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
            {showBase && baseRegion && baseRegion.polygons && baseRegion.polygons.length > 0 && (
              <path className="rf-base" fillRule="evenodd" vectorEffect="non-scaling-stroke"
                    d={ringsToPath(baseRegion.polygons, nb.w, nb.h)} />
            )}
            {proposal && proposal.polygons && proposal.polygons.length > 0 && (
              <path className={`rf-proposal ${reduced ? 'is-static' : ''}`} fillRule="evenodd"
                    vectorEffect="non-scaling-stroke" d={ringsToPath(proposal.polygons, nb.w, nb.h)} />
            )}
            {b && (
              <rect className="rf-boxprompt" vectorEffect="non-scaling-stroke"
                    x={Math.min(b.x0, b.x1) * nb.w} y={Math.min(b.y0, b.y1) * nb.h}
                    width={Math.abs(b.x1 - b.x0) * nb.w} height={Math.abs(b.y1 - b.y0) * nb.h} />
            )}
            {points.map((p, i) => (
              <g key={i} className={`rf-pt ${p.label ? 'is-pos' : 'is-neg'}`}
                 transform={`translate(${p.x * nb.w},${p.y * nb.h})`}>
                <circle r={mk} vectorEffect="non-scaling-stroke" />
                <line x1={-mk} y1="0" x2={mk} y2="0" vectorEffect="non-scaling-stroke" />
                {p.label === 1 && <line x1="0" y1={-mk} x2="0" y2={mk} vectorEffect="non-scaling-stroke" />}
              </g>
            ))}
          </svg>
        )}
        {status === 'loading' && <div className="refine-loading" aria-hidden="true"><span className="rf-spin big" /></div>}
      </div>
    </div>
  );
}
