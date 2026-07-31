import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

// The whole svgr contract, proved on ONE glyph before the other twenty are
// copied (per the migration spec). Both import modes must work, and svgr must
// NOT have stripped the root id or hoisted/minified the per-glyph <style> —
// that scoping is how 21 glyphs coexist in one document.
//   component: named ReactComponent from the plain path (hover/theme reach it)
//   url:       vite's `?url` query (favicon / OG / <img> / print)
import { ReactComponent as Differential } from '@/assets/glyphs/07-differential.svg';
import diffUrl from '@/assets/glyphs/07-differential.svg?url';

describe('svgr — 07-differential (proof glyph)', () => {
  let container;
  beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); });
  afterEach(() => { container.remove(); });

  it('default export is the asset URL', () => {
    expect(typeof diffUrl).toBe('string');
    expect(diffUrl).toMatch(/07-differential\.svg/);
  });

  it('ReactComponent inlines with root id, scoped <style> and filter defs intact', () => {
    const root = createRoot(container);
    act(() => { root.render(<Differential className="glyph" />); });

    // root id survived (not cleaned by SVGO)
    const svg = container.querySelector('svg#g-differential');
    expect(svg).toBeTruthy();

    // the per-glyph scoped <style> survived verbatim (not stripped/hoisted/minified)
    const style = container.querySelector('style');
    expect(style).toBeTruthy();
    expect(style.textContent).toContain('#g-differential{color:#1E1A1C}');

    // a coordinate-bearing filter def survived (proves paths weren't rewritten)
    expect(container.querySelector('filter#differential-bA')).toBeTruthy();

    // the className prop reached the root (component form is themeable/hoverable)
    expect(svg.getAttribute('class')).toContain('glyph');

    act(() => { root.unmount(); });
  });
});
