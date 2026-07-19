import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from '../differential/useStageGeometry';
import useMaskRefine from '../differential/useMaskRefine';
import { ringsToPath } from '../lib/maskGeometry';
import './RefineSurface.css';

/**
 * RefineSurface (VISION-BUILD-001 B4) — the lab harness for the exact-mask refinement
 * loop. It now consumes the shared `useMaskRefine` hook (VISION-B5), so this and the
 * in-product Differential Refine tool run identical logic. Kept as a test harness at
 * `lab/refine/:postId`; the real curator flow lives in DifferentialWorkspace.
 *
 * Stage pan / image drag is prevented while prompting (preventDefault + pointer-events +
 * touch-action + no user-drag), on the shared viewBox=natural / xMidYMid-meet contract.
 */

const reducedMotion = () =>
  typeof window !== 'undefined' && !!window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function RefineSurface({ post, postId, onConfirmed }) {
  const id = postId || post?._id || post?.id;
  const stageRef = useRef(null);
  const [natural, onImgLoad] = useNaturalSize();
  const { content } = useStageGeometry(stageRef, natural);

  const baseRegion = useMemo(
    () => (post?.region_annotations || []).find((r) => r.mask_rle || (r.polygons && r.polygons.length)) || null,
    [post]);

  const refine = useMaskRefine(id, baseRegion);
  const { points, box, proposal, status, error } = refine;

  const [tool, setTool] = useState('point');       // 'point' | 'box'
  const [negative, setNegative] = useState(false);
  const [draftBox, setDraftBox] = useState(null);
  const [showBase, setShowBase] = useState(true);
  const drawing = useRef(false);
  const reduced = reducedMotion();
  const nb = natural || { w: 1, h: 1 };

  const toNorm = (e) => pointerToNormalized(e, stageRef.current, content, { clamp: true });

  const onPointerDown = (e) => {
    if (!content) return;
    e.preventDefault();
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
      if (b && Math.abs(b.x1 - b.x0) > 0.012 && Math.abs(b.y1 - b.y0) > 0.012) refine.setBoxPrompt(b);
    }
  };
  const onClick = (e) => {
    if (tool !== 'point' || !content) return;
    e.preventDefault();
    const p = toNorm(e); if (!p) return;
    refine.addPoint(p.x, p.y, (negative || e.shiftKey || e.altKey) ? 0 : 1);
  };

  const confirm = useCallback(async () => {
    const data = await refine.confirm();
    if (data?.region) onConfirmed?.(data.region, data.post);
  }, [refine, onConfirmed]);
  const cancel = useCallback(() => { refine.clear(); onConfirmed?.(null); }, [refine, onConfirmed]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') refine.clear();
      else if (e.key === 'Enter') confirm();
      else if (e.key === 'b' || e.key === 'B') setTool('box');
      else if (e.key === 'p' || e.key === 'P') setTool('point');
      else if (e.key === 'n' || e.key === 'N') setNegative((v) => !v);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [refine, confirm]);

  // release the SAM session when the harness unmounts.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- depend on stable refine.release, not the object
  useEffect(() => () => { refine.release(); }, [refine.release]);

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
          <button className="rf-btn" onClick={() => refine.clear()}>Clear <kbd>Esc</kbd></button>
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
