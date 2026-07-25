import React, { useEffect, useRef } from 'react';
import sceneRaw from './near-arrival.svg?raw';
import './NearArrival.css';

/**
 * The Near Arrival — the animated hero scene.
 *
 * Ported from `scene/near-arrival.svg` with exactly three changes (per the
 * migration spec); everything else — the five field regions, the seven
 * trajectory sections, the filters, and the stage-1..5 gate classes — is the
 * source SVG, unretyped:
 *
 *  1. The SVG (with its scoped <style> intact) is injected verbatim via
 *     dangerouslySetInnerHTML. Keeping it as a byte-identical .svg on disk and
 *     `?raw`-importing it means not one of its ~330 path coordinates is
 *     retyped — the strongest reading of "assets move as files, nothing is
 *     retyped". Only the trailing inline <script> is stripped, because its
 *     logic moves into the effect below.
 *  2. The <script>'s IntersectionObserver becomes the effect: it adds `play`
 *     once the scene scrolls into view, then stops observing. The
 *     prefers-reduced-motion guard is kept — under it the effect returns before
 *     adding `play`, so the scene rests in its static composed state (which the
 *     art is authored to read as its own afterimage still).
 *  3. The pointer parallax (index.html's trailing script) joins the same
 *     effect, keeping the `pointer:fine` guard and the requestAnimationFrame
 *     throttle. Fields/stars/ink drift at 3/5/8 (x) and 2/3/4 (y).
 *
 * The stage classes are kept in production on purpose — they cost nothing and
 * are how the scene gets re-judged (freeze it at stage-1..5) later.
 */

// The scene, minus its inline <script> (its work is done in the effect). Built
// once at module load; the string is constant so React never re-injects it.
const SCENE_HTML = sceneRaw.replace(/<script[\s\S]*?<\/script>/i, '');

export default function NearArrival() {
  const rootRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const svg = root.querySelector('#scene-near-arrival');
    if (!svg) return;

    // Reduced motion → leave the scene in its composed still. No play, no drift.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // 1 · play once, when the scene is a third on screen, then stop watching.
    const play = () => svg.classList.add('play');
    let io = null;
    if ('IntersectionObserver' in window) {
      io = new IntersectionObserver((entries) => {
        entries.forEach((e) => { if (e.isIntersecting) { play(); io.disconnect(); } });
      }, { threshold: 0.3 });
      io.observe(svg);
    } else {
      play();
    }

    // 2 · pointer parallax — fine pointers only, rAF-throttled.
    let teardownParallax = null;
    if (window.matchMedia('(pointer:fine)').matches) {
      const f = svg.querySelector('.fields');
      const s = svg.querySelector('.stars');
      const k = svg.querySelector('.ink');
      let tx = 0, ty = 0, raf = null;
      const apply = () => {
        raf = null;
        if (f) f.style.transform = `translate(${(tx * 3).toFixed(2)}px,${(ty * 2).toFixed(2)}px)`;
        if (s) s.style.transform = `translate(${(tx * 5).toFixed(2)}px,${(ty * 3).toFixed(2)}px)`;
        if (k) k.style.transform = `translate(${(tx * 8).toFixed(2)}px,${(ty * 4).toFixed(2)}px)`;
      };
      const onMove = (e) => {
        const r = svg.getBoundingClientRect();
        if (r.bottom < 0 || r.top > window.innerHeight) return;
        tx = (e.clientX / window.innerWidth - 0.5) * 2;
        ty = (e.clientY / window.innerHeight - 0.5) * 2;
        if (!raf) raf = requestAnimationFrame(apply);
      };
      window.addEventListener('pointermove', onMove, { passive: true });
      teardownParallax = () => {
        window.removeEventListener('pointermove', onMove);
        if (raf) cancelAnimationFrame(raf);
      };
    }

    return () => {
      if (io) io.disconnect();
      if (teardownParallax) teardownParallax();
    };
  }, []);

  return <div ref={rootRef} className="na-root" dangerouslySetInnerHTML={{ __html: SCENE_HTML }} />;
}
