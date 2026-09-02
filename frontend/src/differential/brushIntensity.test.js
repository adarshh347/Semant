import { describe, it, expect } from 'vitest';
import {
    BRUSH_INTENSITY_LEVELS, INTENSITY_LEVELS, DEFAULT_INTENSITY_LEVEL,
    LEGACY_INTENSITY_LEVEL, DEFAULT_STRENGTH, INTENSITY_RECIPES,
    isIntensityLevel, normalizeIntensityLevel, authoredLevelOf, renderLevelOf,
    isLegacyStroke, withIntensity, levelsUsedBy, levelsAuthoredBy,
    intensityAnatomy, levelsSummary, stampAlphaFor, intensityPasses,
    intensityReadingsOf, readingsFor, setIntensityReading, pruneIntensityReadings,
} from './brushIntensity';

const add = (level, extra = {}) => ({ points: [[0.5, 0.5, 0]], radius: 0.04, strength: 0.8, op: 'add', ...(level !== null ? { intensity_level: level } : {}), ...extra });
const sub = (extra = {}) => ({ points: [[0.2, 0.2, 0]], radius: 0.03, op: 'sub', ...extra });

describe('the vocabulary', () => {
    it('is exactly four ordinal levels with stable keys and labels', () => {
        expect(BRUSH_INTENSITY_LEVELS.map((l) => l.level)).toEqual([1, 2, 3, 4]);
        expect(BRUSH_INTENSITY_LEVELS.map((l) => l.key)).toEqual(['trace', 'supporting', 'structural', 'dominant']);
        expect(BRUSH_INTENSITY_LEVELS.map((l) => l.label)).toEqual(['Trace', 'Supporting', 'Structural', 'Dominant']);
        expect(INTENSITY_LEVELS).toEqual([1, 2, 3, 4]);
    });

    it('defaults new work to 3, and reads legacy work as 3', () => {
        expect(DEFAULT_INTENSITY_LEVEL).toBe(3);
        expect(LEGACY_INTENSITY_LEVEL).toBe(3);
    });
});

describe('validation is by rejection, never by rounding', () => {
    it('accepts only the four integers', () => {
        for (const v of [1, 2, 3, 4]) expect(isIntensityLevel(v)).toBe(true);
    });

    // The whole point: 3.5 is not "about 4". Rounding an invalid authored value
    // would let it masquerade as a level the curator never chose.
    it.each([0, 5, 3.5, 2.0001, -1, Infinity, NaN, '3', true, false, null, undefined, {}, []])(
        'rejects %p rather than coercing it', (bad) => {
            expect(isIntensityLevel(bad)).toBe(false);
            expect(normalizeIntensityLevel(bad)).toBeNull();
        });

    it('does not let a near-miss round into a neighbouring level', () => {
        expect(normalizeIntensityLevel(3.5)).toBeNull();
        expect(normalizeIntensityLevel(3.5)).not.toBe(4);
        expect(normalizeIntensityLevel(0.9)).not.toBe(1);
    });
});

describe('a level is authored, and only on additive strokes', () => {
    it('stamps the selected level onto a new additive stroke', () => {
        expect(withIntensity(add(null), 2).intensity_level).toBe(2);
    });

    it('omits the key on an erase — erasing edits geometry, it asserts no register', () => {
        expect('intensity_level' in withIntensity(sub(), 4)).toBe(false);
        expect(authoredLevelOf(sub({ intensity_level: 4 }))).toBeNull();
    });

    it('strips a level that a caller tried to put on a subtractive stroke', () => {
        expect('intensity_level' in withIntensity(sub({ intensity_level: 2 }), 2)).toBe(false);
    });

    it('refuses to stamp an invalid level, leaving the stroke untouched', () => {
        const s = add(null);
        expect(withIntensity(s, 3.5)).toBe(s);
        expect(withIntensity(s, 9)).toBe(s);
    });

    it('never mutates the stroke it is given', () => {
        const s = add(null);
        withIntensity(s, 4);
        expect('intensity_level' in s).toBe(false);
    });
});

describe('legacy strokes load, render, and are not rewritten', () => {
    it('renders a stroke with no level at the documented legacy default', () => {
        expect(renderLevelOf(add(null))).toBe(3);
        expect(authoredLevelOf(add(null))).toBeNull();
    });

    it('renders an INVALID stored level as legacy rather than throwing or rounding', () => {
        expect(renderLevelOf(add(7))).toBe(3);
        expect(renderLevelOf(add(2.5))).toBe(3);
        expect(authoredLevelOf(add(7))).toBeNull();
    });

    it('stays identifiable as ungraded — legacy is a read, not a silent upgrade', () => {
        expect(isLegacyStroke(add(null))).toBe(true);
        expect(isLegacyStroke(add(3))).toBe(false);      // authored 3 ≠ legacy 3
        expect(levelsAuthoredBy({ strokes: [add(null)] })).toEqual([]);
        expect(levelsUsedBy({ strokes: [add(null)] })).toEqual([3]);
    });

    it('reading a legacy stroke does not add the field to it', () => {
        const s = add(null);
        renderLevelOf(s); levelsUsedBy({ strokes: [s] }); intensityAnatomy({ strokes: [s] });
        expect(Object.keys(s)).not.toContain('intensity_level');
    });
});

describe('level, radius, pressure and strength stay four separate quantities', () => {
    // The identity that makes this backward-compatible: at level 3 the stamped
    // alpha IS the historical `strength`, for every strength any producer wrote.
    it.each([0.4, 0.8, 0.9, 1.0])('reproduces the historical alpha exactly at level 3 (strength %p)', (st) => {
        expect(stampAlphaFor({ op: 'add', strength: st }, 3)).toBeCloseTo(st, 10);
    });

    it('defaults a strength-less stroke to the historical default', () => {
        expect(stampAlphaFor({ op: 'add' }, 3)).toBeCloseTo(DEFAULT_STRENGTH, 10);
    });

    it('does not derive the level from pressure', () => {
        const heavy = add(1, { points: [[0.5, 0.5, 1.0]] });
        const light = add(4, { points: [[0.5, 0.5, 0.02]] });
        expect(renderLevelOf(heavy)).toBe(1);   // hard press, faint register
        expect(renderLevelOf(light)).toBe(4);   // feather touch, dominant register
    });

    it('does not overwrite the stored integer with the computed render alpha', () => {
        const s = add(1);
        stampAlphaFor(s);
        expect(s.intensity_level).toBe(1);
        expect(s.strength).toBe(0.8);
    });

    it('keeps strength as a multiplier that never changes which level was authored', () => {
        expect(stampAlphaFor(add(1, { strength: 1.0 }))).toBeGreaterThan(stampAlphaFor(add(1, { strength: 0.4 })));
        expect(authoredLevelOf(add(1, { strength: 1.0 }))).toBe(1);
    });
});

describe('the render recipes', () => {
    it('are monotonic — 1 lightest, 4 densest, in every channel', () => {
        const r = INTENSITY_LEVELS.map((l) => INTENSITY_RECIPES[l]);
        for (let i = 1; i < r.length; i++) {
            expect(r[i].core).toBeGreaterThan(r[i - 1].core);
            expect(r[i].body).toBeGreaterThan(r[i - 1].body);
            expect(r[i].rimBlur).toBeGreaterThan(r[i - 1].rimBlur);
        }
    });

    it('keeps adjacent levels separated by a real margin, not a hairline', () => {
        const r = INTENSITY_LEVELS.map((l) => INTENSITY_RECIPES[l]);
        for (let i = 1; i < r.length; i++) {
            expect(r[i].body - r[i - 1].body).toBeGreaterThanOrEqual(0.08);
        }
    });

    it('carries a contour at EVERY level — alpha alone collapses on light pixels', () => {
        for (const l of INTENSITY_LEVELS) expect(INTENSITY_RECIPES[l].rimBlur).toBeGreaterThan(0);
    });

    it('reproduces the pre-vocabulary appearance exactly at level 3', () => {
        expect(INTENSITY_RECIPES[3]).toMatchObject({ core: 0.8, body: 0.46, rimBlur: 3.5, rimBoost: 0 });
    });

    it('introduces no hue channel — the recipes carry weight only', () => {
        for (const l of INTENSITY_LEVELS) {
            expect(Object.keys(INTENSITY_RECIPES[l])).toEqual(
                expect.not.arrayContaining(['hue', 'color', 'colour', 'accent']));
        }
    });

    it('stays a soft field — no level paints an opaque blob', () => {
        for (const l of INTENSITY_LEVELS) expect(INTENSITY_RECIPES[l].body).toBeLessThan(0.75);
    });
});

describe('the anatomy a field reports', () => {
    const ground = { strokes: [add(1), add(3), add(1), sub(), add(4)] };

    it('lists only the levels actually used, ascending', () => {
        expect(levelsUsedBy(ground)).toEqual([1, 3, 4]);
    });

    it('counts additive strokes per level and ignores erases', () => {
        expect(intensityAnatomy(ground).levels).toEqual([
            { level: 1, label: 'Trace', count: 2 },
            { level: 3, label: 'Structural', count: 1 },
            { level: 4, label: 'Dominant', count: 1 },
        ]);
    });

    it('reports ungraded strokes separately rather than hiding them', () => {
        expect(intensityAnatomy({ strokes: [add(null), add(2)] }).legacyCount).toBe(1);
    });

    it('summarises for the draft status line', () => {
        expect(levelsSummary(ground.strokes)).toBe('levels 1, 3, 4');
        expect(levelsSummary([])).toBe('');
        expect(levelsSummary([sub()])).toBe('');   // erases alone assert nothing
    });

    it('tolerates a missing/empty ground', () => {
        expect(levelsUsedBy(null)).toEqual([]);
        expect(intensityAnatomy(undefined).levels).toEqual([]);
    });
});

describe('the compositing policy — where four levels could flatten into one wash', () => {
    it('emits one pass per used level, in ascending order', () => {
        const passes = intensityPasses({ strokes: [add(4), add(1), add(4), add(2)] });
        expect(passes.map((p) => p.level)).toEqual([1, 2, 4]);
        expect(passes.map((p) => p.add.length)).toEqual([1, 1, 2]);
    });

    // Two curators who paint the same anatomy in a different sequence must get
    // the same image. Draw order is a function of the level, not of authoring.
    it('is independent of the order the strokes were painted in', () => {
        const a = intensityPasses({ strokes: [add(1), add(4), add(2)] });
        const b = intensityPasses({ strokes: [add(4), add(2), add(1)] });
        expect(a.map((p) => p.level)).toEqual(b.map((p) => p.level));
        expect(a.map((p) => p.recipe)).toEqual(b.map((p) => p.recipe));
    });

    it('gives every pass its own recipe — the levels never share one alpha', () => {
        const passes = intensityPasses({ strokes: [add(1), add(4)] });
        expect(passes[0].recipe.body).not.toBe(passes[1].recipe.body);
        expect(passes[0].recipe).toBe(INTENSITY_RECIPES[1]);
        expect(passes[1].recipe).toBe(INTENSITY_RECIPES[4]);
    });

    // An erase alters the field's geometry, so it must cut every register it
    // crosses — not just whichever was selected when the curator erased.
    it('carries the ground\'s FULL subtractive set into every level pass', () => {
        const s1 = sub(), s2 = sub();
        const passes = intensityPasses({ strokes: [add(1), s1, add(3), s2] });
        expect(passes).toHaveLength(2);
        for (const p of passes) expect(p.sub).toEqual([s1, s2]);
    });

    it('emits no pass for a field of erases alone', () => {
        expect(intensityPasses({ strokes: [sub(), sub()] })).toEqual([]);
    });

    it('folds legacy and authored-3 strokes into the single level-3 pass', () => {
        const passes = intensityPasses({ strokes: [add(null), add(3)] });
        expect(passes).toHaveLength(1);
        expect(passes[0].level).toBe(3);
        expect(passes[0].add).toHaveLength(2);
    });

    it('stamps each stroke at its own level\'s core, not a shared one', () => {
        const passes = intensityPasses({ strokes: [add(1), add(4)] });
        const alphas = passes.map((p) => stampAlphaFor(p.add[0], p.level));
        expect(alphas[0]).toBeLessThan(alphas[1]);
        expect(alphas[0]).toBeCloseTo(INTENSITY_RECIPES[1].core, 10);
    });
});

describe('per-level phrases live on the percept, not on the ground', () => {
    const percept = { id: 'pctx_1', ground_ids: ['gnd_a', 'gnd_b'] };
    const field = { id: 'gnd_a', ground_type: 'field', strokes: [add(1), add(3)] };

    it('sets a phrase for a level the cited field actually uses', () => {
        const p = setIntensityReading(percept, 'gnd_a', 1, 'neckline threshold', field);
        expect(p.ground_intensity_readings).toEqual({ gnd_a: { 1: 'neckline threshold' } });
    });

    it('refuses a level that field does not use — a reading of absent evidence', () => {
        expect(setIntensityReading(percept, 'gnd_a', 4, 'answering hand', field)).toBe(percept);
    });

    it('refuses a ground the percept does not cite', () => {
        expect(setIntensityReading(percept, 'gnd_zz', 1, 'x', field)).toBe(percept);
    });

    it('refuses an invalid level', () => {
        expect(setIntensityReading(percept, 'gnd_a', 3.5, 'x', field)).toBe(percept);
    });

    it('never writes to the ground record', () => {
        const before = JSON.stringify(field);
        setIntensityReading(percept, 'gnd_a', 1, 'neckline threshold', field);
        expect(JSON.stringify(field)).toBe(before);
    });

    it('omits the key entirely when the last phrase is cleared — byte-identical to never having used it', () => {
        let p = setIntensityReading(percept, 'gnd_a', 1, 'neckline threshold', field);
        p = setIntensityReading(p, 'gnd_a', 1, '', field);
        expect('ground_intensity_readings' in p).toBe(false);
        expect(p).toEqual(percept);
    });

    it('treats a whitespace-only phrase as a clear, not as a phrase', () => {
        const p = setIntensityReading(percept, 'gnd_a', 1, '   ', field);
        expect('ground_intensity_readings' in p).toBe(false);
    });

    it('reads tolerantly — absent, null, or an array all yield {}', () => {
        expect(intensityReadingsOf(null)).toEqual({});
        expect(intensityReadingsOf({})).toEqual({});
        expect(intensityReadingsOf({ ground_intensity_readings: null })).toEqual({});
        expect(intensityReadingsOf({ ground_intensity_readings: [] })).toEqual({});
    });

    it('drops junk levels and non-string phrases on read', () => {
        const r = intensityReadingsOf({
            ground_intensity_readings: { gnd_a: { 1: 'ok', 9: 'nope', x: 'nope', 2: 42, 3: '  ' } },
        });
        expect(r).toEqual({ gnd_a: { 1: 'ok' } });
    });

    it('reads back one ground\'s phrases', () => {
        const p = setIntensityReading(percept, 'gnd_a', 3, 'answering hand', field);
        expect(readingsFor(p, 'gnd_a')).toEqual({ 3: 'answering hand' });
        expect(readingsFor(p, 'gnd_b')).toEqual({});
    });

    it('survives a round trip through JSON — the reload requirement', () => {
        let p = setIntensityReading(percept, 'gnd_a', 1, 'neckline threshold', field);
        p = setIntensityReading(p, 'gnd_a', 3, 'answering hand', field);
        expect(intensityReadingsOf(JSON.parse(JSON.stringify(p)))).toEqual({
            gnd_a: { 1: 'neckline threshold', 3: 'answering hand' },
        });
    });
});

describe('pruning keeps a phrase from outliving its evidence', () => {
    const byId = (g) => ({ gnd_a: { strokes: [add(1), add(3)] } }[g] || null);

    it('drops a level whose strokes were erased away since it was typed', () => {
        const out = pruneIntensityReadings({ gnd_a: { 1: 'keep', 4: 'gone' } },
            { ground_ids: ['gnd_a'], groundById: byId });
        expect(out).toEqual({ gnd_a: { 1: 'keep' } });
    });

    it('drops a ground the percept no longer cites', () => {
        expect(pruneIntensityReadings({ gnd_zz: { 1: 'x' } },
            { ground_ids: ['gnd_a'], groundById: byId })).toEqual({});
    });

    it('returns {} for empty input rather than a stray key', () => {
        expect(pruneIntensityReadings(null, { ground_ids: [], groundById: byId })).toEqual({});
    });
});
