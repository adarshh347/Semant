/**
 * The renderer, against a RECORDING fake 2D context.
 *
 * Named `.dom.test.jsx` because it needs a document (vite.config.js opts these
 * into jsdom by name). jsdom has no canvas, and a markup snapshot cannot see a wash. These tests
 * assert what actually reaches the context — how many tinted passes, at which
 * alphas, in which order — because the failure this refactor exists to prevent
 * (four authored levels averaged into one uniform wash at the final step) is
 * invisible to every other kind of test.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { paintFields } from './fieldCanvas';
import { INTENSITY_RECIPES } from './brushIntensity';

const add = (level, extra = {}) => ({ points: [[0.5, 0.5, 1]], radius: 0.04, strength: 0.8, op: 'add', ...(level !== null ? { intensity_level: level } : {}), ...extra });
const sub = (extra = {}) => ({ points: [[0.3, 0.3, 1]], radius: 0.03, op: 'sub', ...extra });

/** Records the composite pass log: every drawImage with the state it ran under. */
function makeCtx(log, tag) {
    const ctx = {
        globalAlpha: 1, globalCompositeOperation: 'source-over',
        shadowColor: '', shadowBlur: 0, fillStyle: '',
        _stack: [],
        save() { this._stack.push({ a: this.globalAlpha, sc: this.shadowColor, sb: this.shadowBlur }); },
        restore() { const s = this._stack.pop(); if (s) { this.globalAlpha = s.a; this.shadowColor = s.sc; this.shadowBlur = s.sb; } },
        clearRect: () => log.push({ tag, op: 'clear' }),
        fillRect() { log.push({ tag, op: 'fill', composite: this.globalCompositeOperation, fillStyle: this.fillStyle }); },
        beginPath() {}, arc() {}, fill() {},
        createRadialGradient() {
            const stops = [];
            return { addColorStop: (o, c) => stops.push([o, c]), _stops: stops };
        },
        drawImage() {
            log.push({ tag, op: 'draw', alpha: this.globalAlpha, shadowBlur: this.shadowBlur, shadowColor: this.shadowColor });
        },
    };
    return ctx;
}

let log;
function stageCanvas() {
    log = [];
    // The offscreen buffer created inside paintFields.
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
        if (tag !== 'canvas') return document.createElementNS('http://www.w3.org/1999/xhtml', tag);
        return { width: 0, height: 0, getContext: () => makeCtx(log, 'buffer') };
    });
    return { width: 0, height: 0, getContext: () => makeCtx(log, 'stage') };
}

const CONTENT = { x: 0, y: 0, w: 400, h: 300 };
const draws = () => log.filter((e) => e.tag === 'stage' && e.op === 'draw');
const tints = () => log.filter((e) => e.tag === 'buffer' && e.op === 'fill' && e.composite === 'source-in');

/**
 * Draws grouped into level PASSES. Each pass begins with a buffer clear, so the
 * log's own ordering recovers the grouping. A pass may draw more than once: the
 * densest level repeats to deepen its contour, which is why a flat draw count is
 * the wrong unit and the body alpha is `pass[0]`.
 */
function passes() {
    const out = [];
    for (const e of log) {
        if (e.tag === 'buffer' && e.op === 'clear') out.push([]);
        else if (e.tag === 'stage' && e.op === 'draw' && out.length) out[out.length - 1].push(e);
    }
    return out.filter((p) => p.length);
}
const bodyAlphas = () => passes().map((p) => p[0].alpha);

beforeEach(() => { vi.restoreAllMocks(); window.devicePixelRatio = 1; });

describe('one tinted pass per used level', () => {
    it('draws three separate passes for a three-register field', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(2), add(4)] } }], CONTENT, { color: '#5E2B50' });
        expect(passes()).toHaveLength(3);
        expect(tints()).toHaveLength(3);
    });

    it('draws ONE pass for a single-register field (no gratuitous extra work)', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(2), add(2)] } }], CONTENT);
        expect(passes()).toHaveLength(1);
    });

    // THE REGRESSION THIS FILE EXISTS FOR. The old renderer tinted the combined
    // mask once at one alpha; four levels would have arrived and been averaged.
    it('does NOT collapse distinct levels into one uniform alpha', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(2), add(3), add(4)] } }], CONTENT);
        const alphas = draws().map((d) => d.alpha);
        expect(new Set(alphas).size).toBeGreaterThan(1);
    });

    it('paints ascending — lightest first, densest last, whatever the paint order', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(4), add(1), add(3)] } }], CONTENT);
        // Body alphas, one per pass — the densest level's extra contour pass is
        // part of that level, not a fifth register.
        const alphas = bodyAlphas();
        expect(alphas).toEqual([...alphas].sort((a, b) => a - b));
    });

    it('gives the same image regardless of the order strokes were painted in', () => {
        const c1 = stageCanvas();
        paintFields(c1, [{ ground: { strokes: [add(1), add(4)] } }], CONTENT);
        const first = draws().map((d) => ({ alpha: d.alpha, shadowBlur: d.shadowBlur }));
        const c2 = stageCanvas();
        paintFields(c2, [{ ground: { strokes: [add(4), add(1)] } }], CONTENT);
        expect(draws().map((d) => ({ alpha: d.alpha, shadowBlur: d.shadowBlur }))).toEqual(first);
    });
});

describe('each pass uses its own recipe', () => {
    it('draws each level at its recipe body alpha', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(3)] } }], CONTENT);
        const alphas = bodyAlphas();
        expect(alphas[0]).toBeCloseTo(INTENSITY_RECIPES[1].body, 6);
        expect(alphas[0]).toBeLessThan(alphas[1]);
    });

    it('carries a contour on every pass — the channel that survives light pixels', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(2), add(3), add(4)] } }], CONTENT);
        for (const d of draws()) {
            expect(d.shadowBlur).toBeGreaterThan(0);
            expect(d.shadowColor).toBeTruthy();
        }
    });

    it('gives the densest level its extra contour pass', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(4)] } }], CONTENT);
        expect(passes()).toHaveLength(1);
        expect(passes()[0]).toHaveLength(2);   // body + contour
        expect(passes()[0][1].alpha).toBeCloseTo(INTENSITY_RECIPES[4].rimBoost, 6);
    });

    it('tints with the accent, never a per-level hue', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(4)] } }], CONTENT, { color: '#5E2B50' });
        const fills = tints().map((f) => f.fillStyle);
        expect(new Set(fills)).toEqual(new Set(['#5E2B50']));
    });
});

describe('legacy fields render exactly as they always did', () => {
    it('draws an ungraded field as a single level-3 pass at the historical alpha', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(null), add(null)] } }], CONTENT);
        expect(passes()).toHaveLength(1);
        expect(draws()).toHaveLength(1);
        expect(draws()[0].alpha).toBeCloseTo(0.46, 6);      // the historical WASH_ALPHA
        expect(draws()[0].shadowBlur).toBeCloseTo(3.5, 6);  // the historical RIM_BLUR
    });

    it('does not mutate the strokes it renders', () => {
        const canvas = stageCanvas();
        const strokes = [add(null), add(2)];
        const before = JSON.stringify(strokes);
        paintFields(canvas, [{ ground: { strokes } }], CONTENT);
        expect(JSON.stringify(strokes)).toBe(before);
    });
});

describe('erase stays honest across the anatomy', () => {
    it('applies the subtractive strokes inside EVERY level pass', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(4), sub()] } }], CONTENT);
        // Two levels → two buffer clears, and the erase is stamped within each.
        expect(passes()).toHaveLength(2);
        expect(draws()).toHaveLength(3);   // level 1, level 4 body, level 4 contour
    });

    it('paints nothing for a field of erases alone', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [sub(), sub()] } }], CONTENT);
        expect(draws()).toHaveLength(0);
    });
});

describe('the level recipe composes with the surrounding state', () => {
    it('scales every pass by layer/focus alpha', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1), add(3)] }, alpha: 0.5 }], CONTENT);
        for (const d of draws()) expect(d.alpha).toBeLessThan(INTENSITY_RECIPES[3].body);
    });

    it('ramps every pass with recall progress', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(4)] }, progress: 0.2 }], CONTENT);
        const full = draws()[0].alpha;
        const canvas2 = stageCanvas();
        paintFields(canvas2, [{ ground: { strokes: [add(4)] }, progress: 1 }], CONTENT);
        expect(draws()[0].alpha).toBeGreaterThan(full);
    });

    it('skips a hidden or fully-dimmed ground entirely', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [{ ground: { strokes: [add(1)] }, alpha: 0 }], CONTENT);
        expect(draws()).toHaveLength(0);
    });

    it('renders several grounds independently, each with its own anatomy', () => {
        const canvas = stageCanvas();
        paintFields(canvas, [
            { ground: { strokes: [add(1)] } },
            { ground: { strokes: [add(2), add(4)] } },
        ], CONTENT);
        expect(passes()).toHaveLength(3);  // level 1 | level 2, level 4
        expect(draws()).toHaveLength(4);   // + level 4's contour pass
    });
});

describe('it never throws where a canvas is unavailable', () => {
    it('returns quietly with no 2D context', () => {
        expect(() => paintFields({ width: 0, height: 0, getContext: () => null }, [{ ground: { strokes: [add(1)] } }], CONTENT)).not.toThrow();
    });

    it('returns quietly before geometry is ready', () => {
        expect(() => paintFields(stageCanvas(), [{ ground: { strokes: [add(1)] } }], null)).not.toThrow();
        expect(() => paintFields(stageCanvas(), [], CONTENT)).not.toThrow();
    });
});
