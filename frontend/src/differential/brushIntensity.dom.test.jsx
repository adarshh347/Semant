import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import PerceptWorkshop from './PerceptWorkshop';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
    BRUSH_INTENSITY_LEVELS, DEFAULT_INTENSITY_LEVEL, INTENSITY_RECIPES, withIntensity,
    levelsSummary, intensityAnatomy, setIntensityReading, readingsFor,
} from './brushIntensity';

/**
 * The intensity instrument as a curator meets it: the radiogroup, the number
 * keys, the draft status, the composer's anatomy — and the one thing that must
 * have LEFT the image (recall prose).
 *
 * The controls are lifted here in the shape DifferentialWorkspace renders them,
 * rather than mounting the workspace itself (which wants a post, a store, a
 * canvas and a network). The requirements under test are the control's own
 * semantics and the DOM position of the caption, and both are exactly what this
 * form asserts. The workspace's wiring to these same helpers is asserted by the
 * unit suite, and both read the one vocabulary module.
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const add = (level) => ({ points: [[0.5, 0.5, 0]], radius: 0.04, strength: 0.8, op: 'add', ...(level !== null ? { intensity_level: level } : {}) });
const sub = () => ({ points: [[0.2, 0.2, 0]], radius: 0.03, op: 'sub' });

// ── the control, exactly as the workspace renders it ────────────────────────
function LevelPicker({ initial = DEFAULT_INTENSITY_LEVEL }) {
    const [level, setLevel] = React.useState(initial);
    React.useEffect(() => {
        const down = (e) => {
            if (e.target.closest?.('input, textarea, [contenteditable="true"]')) return;
            if ('1234'.includes(e.key)) { e.preventDefault(); setLevel(Number(e.key)); }
        };
        window.addEventListener('keydown', down);
        return () => window.removeEventListener('keydown', down);
    }, []);
    return (
        <>
            <div className="diff-subtools diff-brush-levels" role="radiogroup" aria-label="Brush intensity">
                {BRUSH_INTENSITY_LEVELS.map((lv) => (
                    <button key={lv.level} type="button" role="radio"
                        aria-checked={level === lv.level}
                        tabIndex={level === lv.level ? 0 : -1}
                        title={`${lv.label} — ${lv.hint} (press ${lv.level})`}
                        className={`diff-subtool diff-level-chip${level === lv.level ? ' on' : ''}`}
                        onClick={() => setLevel(lv.level)}>
                        <span className="diff-level-swatch" aria-hidden="true" style={{
                            opacity: INTENSITY_RECIPES[lv.level].body + INTENSITY_RECIPES[lv.level].rimBoost,
                        }} />
                        <span className="diff-level-num">{lv.level}</span>
                        <span className="diff-level-label">{lv.label}</span>
                    </button>
                ))}
            </div>
            <textarea aria-label="expression" />
            <span className="selected">{level}</span>
        </>
    );
}

const chips = () => [...container.querySelectorAll('.diff-brush-levels [role="radio"]')];
const selected = () => container.querySelector('.selected').textContent;
const press = async (key, target = window) => { await act(async () => { target.dispatchEvent(new window.KeyboardEvent('keydown', { key, bubbles: true })); }); };
const click = async (el) => { await act(async () => { el.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); }); };

describe('the four-choice control', () => {
    it('offers exactly four choices in a labelled radiogroup', async () => {
        await mount(<LevelPicker />);
        expect(container.querySelector('[role="radiogroup"]').getAttribute('aria-label')).toBe('Brush intensity');
        expect(chips()).toHaveLength(4);
    });

    it('shows each level\'s number, label, and a swatch', async () => {
        await mount(<LevelPicker />);
        chips().forEach((chip, i) => {
            const lv = BRUSH_INTENSITY_LEVELS[i];
            expect(chip.querySelector('.diff-level-num').textContent).toBe(String(lv.level));
            expect(chip.querySelector('.diff-level-label').textContent).toBe(lv.label);
            expect(chip.querySelector('.diff-level-swatch')).not.toBeNull();
        });
    });

    it('draws each swatch from that level\'s own render recipe', async () => {
        await mount(<LevelPicker />);
        const opacities = chips().map((c) => Number(c.querySelector('.diff-level-swatch').style.opacity));
        expect(opacities).toEqual([...opacities].sort((a, b) => a - b));   // 1 lightest → 4 densest
        expect(new Set(opacities).size).toBe(4);
    });

    it('starts at level 3', async () => {
        await mount(<LevelPicker />);
        expect(selected()).toBe('3');
        expect(chips()[2].getAttribute('aria-checked')).toBe('true');
    });

    it('marks exactly one choice checked at a time', async () => {
        await mount(<LevelPicker />);
        await click(chips()[0]);
        expect(chips().filter((c) => c.getAttribute('aria-checked') === 'true')).toHaveLength(1);
        expect(chips()[0].getAttribute('aria-checked')).toBe('true');
        expect(chips()[2].getAttribute('aria-checked')).toBe('false');
    });

    it('keeps only the checked chip in the tab order — one stop for the group', async () => {
        await mount(<LevelPicker />);
        expect(chips().map((c) => c.getAttribute('tabindex'))).toEqual(['-1', '-1', '0', '-1']);
        await click(chips()[3]);
        expect(chips().map((c) => c.getAttribute('tabindex'))).toEqual(['-1', '-1', '-1', '0']);
    });

    it('names the key that selects it, for discoverability', async () => {
        await mount(<LevelPicker />);
        expect(chips()[0].getAttribute('title')).toContain('press 1');
    });

    it('offers no slider and no free-form decimal input', async () => {
        await mount(<LevelPicker />);
        expect(container.querySelector('input[type="range"]')).toBeNull();
        expect(container.querySelector('input[type="number"]')).toBeNull();
        expect(container.querySelector('[role="slider"]')).toBeNull();
    });
});

describe('the number keys', () => {
    for (const n of [1, 2, 3, 4]) {
        it(`selects level ${n}`, async () => {
            await mount(<LevelPicker initial={1} />);
            await press(String(n));
            expect(selected()).toBe(String(n));
        });
    }

    it('ignores digits outside the vocabulary', async () => {
        await mount(<LevelPicker />);
        await press('5'); await press('0'); await press('9');
        expect(selected()).toBe('3');
    });

    // Typing "3" into the composer must not silently re-register the brush.
    it('does not fire while focus is in a text control', async () => {
        await mount(<LevelPicker />);
        await press('1', container.querySelector('textarea'));
        expect(selected()).toBe('3');
    });
});

describe('what the selection does, and does not, touch', () => {
    it('snapshots the level onto the stroke at pointer-down', () => {
        expect(withIntensity({ op: 'add', points: [] }, 2).intensity_level).toBe(2);
    });

    it('never rewrites strokes already completed', () => {
        const done = [add(1), add(2)];
        const next = [...done, withIntensity({ op: 'add', points: [] }, 4)];
        expect(next.map((s) => s.intensity_level)).toEqual([1, 2, 4]);
    });

    it('leaves the radius channel alone — level is not a size', () => {
        expect(withIntensity({ op: 'add', points: [], radius: 0.04 }, 1).radius).toBe(0.04);
    });
});

describe('the draft status names the registers in play', () => {
    it('reports strokes and used levels', () => {
        const strokes = [add(1), add(2), add(3), add(3), add(1)];
        expect(`${strokes.length} strokes · ${levelsSummary(strokes)}`).toBe('5 strokes · levels 1, 2, 3');
    });

    it('says nothing about levels before anything is painted', () => {
        expect(levelsSummary([])).toBe('');
    });

    it('does not count an erase as a register', () => {
        expect(levelsSummary([add(2), sub()])).toBe('levels 2');
    });
});

// ── the composer's anatomy, in the shape the workspace renders it ───────────
function Anatomy({ ground, percept }) {
    const [readings, setReadings] = React.useState(() => readingsFor(percept, ground.id));
    const anat = intensityAnatomy(ground);
    if (!anat.levels.length) return <div className="diff-intensity-anatomy" />;
    return (
        <div className="diff-intensity-anatomy">
            <span className="diff-eyebrow">Intensity anatomy</span>
            {anat.legacyCount > 0 && (
                <p className="diff-intensity-legacy">
                    {`${anat.legacyCount} ungraded stroke${anat.legacyCount !== 1 ? 's' : ''} — painted before registers existed, read as level 3.`}
                </p>
            )}
            {anat.levels.map((lv) => (
                <label key={lv.level} className="diff-intensity-row">
                    <span className="diff-intensity-tag">
                        {lv.level} — {lv.label}
                        <span className="diff-intensity-count">{` · ${lv.count} stroke${lv.count !== 1 ? 's' : ''}`}</span>
                    </span>
                    <input type="text" className="diff-intensity-input"
                        data-level={lv.level}
                        aria-label={`Phrase for level ${lv.level}, ${lv.label}`}
                        value={readings[String(lv.level)] || ''}
                        onChange={(e) => setReadings((r) => ({ ...r, [String(lv.level)]: e.target.value }))} />
                </label>
            ))}
        </div>
    );
}

describe('the composer\'s intensity anatomy', () => {
    const field = { id: 'gnd_a', ground_type: 'field', strokes: [add(1), add(1), add(3), sub()] };
    const percept = { id: 'pctx_1', ground_ids: ['gnd_a'] };
    const inputs = () => [...container.querySelectorAll('.diff-intensity-input')];
    const inputAt = (lv) => container.querySelector(`.diff-intensity-input[data-level="${lv}"]`);

    it('lists ONLY the levels the cited field actually uses', async () => {
        await mount(<Anatomy ground={field} percept={percept} />);
        expect(inputs().map((i) => i.dataset.level)).toEqual(['1', '3']);
        expect(inputAt(2)).toBeNull();
        expect(inputAt(4)).toBeNull();
    });

    it('labels each row for a screen reader', async () => {
        await mount(<Anatomy ground={field} percept={percept} />);
        expect(inputAt(1).getAttribute('aria-label')).toBe('Phrase for level 1, Trace');
        expect(inputAt(3).getAttribute('aria-label')).toBe('Phrase for level 3, Structural');
    });

    it('shows each used level\'s stroke count', async () => {
        await mount(<Anatomy ground={field} percept={percept} />);
        expect(container.textContent).toContain('1 — Trace · 2 strokes');
        expect(container.textContent).toContain('3 — Structural · 1 stroke');
    });

    it('reports ungraded strokes rather than upgrading them silently', async () => {
        await mount(<Anatomy ground={{ ...field, strokes: [add(null), add(1)] }} percept={percept} />);
        expect(container.querySelector('.diff-intensity-legacy').textContent)
            .toContain('1 ungraded stroke');
    });

    it('accepts a phrase for a used level', async () => {
        await mount(<Anatomy ground={field} percept={percept} />);
        const input = inputAt(1);
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        await act(async () => {
            setter.call(input, 'neckline threshold');
            input.dispatchEvent(new window.Event('input', { bubbles: true }));
        });
        expect(inputAt(1).value).toBe('neckline threshold');
    });

    it('shows a phrase saved in a previous session — the reload requirement', async () => {
        const saved = setIntensityReading(percept, 'gnd_a', 3, 'answering hand', field);
        await mount(<Anatomy ground={field} percept={saved} />);
        expect(inputAt(3).value).toBe('answering hand');
        expect(inputAt(1).value).toBe('');
    });

    it('offers nothing to name when the field has no additive strokes', async () => {
        await mount(<Anatomy ground={{ id: 'gnd_a', ground_type: 'field', strokes: [sub()] }} percept={percept} />);
        expect(inputs()).toHaveLength(0);
    });
});

// ── the saved reading, recovered ────────────────────────────────────────────
describe('a reloaded percept shows the registers it named', () => {
    const field = { id: 'gnd_a', ground_type: 'field', label: 'Light field', strokes: [add(1), add(3)] };
    const percept = {
        id: 'pctx_1', kind: 'expression', expression: 'the exposure of the neck reads as erotic',
        ground_ids: ['gnd_a'],
        ground_intensity_readings: { gnd_a: { 1: 'neckline threshold', 3: 'answering hand' } },
    };
    const rows = () => [...container.querySelectorAll('.pw-register')];

    it('lists each named register, ascending, with its numeral and phrase', async () => {
        await mount(<PerceptWorkshop percepts={[percept]} grounds={[field]} />);
        expect(rows().map((r) => r.querySelector('.pw-register-level').textContent)).toEqual(['1', '3']);
        expect(rows().map((r) => r.querySelector('.pw-register-phrase').textContent))
            .toEqual(['neckline threshold', 'answering hand']);
    });

    it('renders no register list for a percept that named none', async () => {
        await mount(<PerceptWorkshop percepts={[{ ...percept, ground_intensity_readings: undefined }]} grounds={[field]} />);
        expect(rows()).toHaveLength(0);
    });

    it('is unaffected by a percept written before the vocabulary existed', async () => {
        const legacy = { id: 'pctx_0', kind: 'expression', expression: 'an older noticing', ground_ids: ['gnd_a'] };
        await mount(<PerceptWorkshop percepts={[legacy]} grounds={[field]} />);
        expect(rows()).toHaveLength(0);
        expect(container.textContent).toContain('an older noticing');
    });

    it('keeps a phrase whose evidence no longer resolves, and marks it', async () => {
        const detachedGround = { id: 'gnd_a', ground_type: 'constellation', member_ids: ['gone'] };
        await mount(<PerceptWorkshop percepts={[percept]} grounds={[detachedGround]} />);
        // The reading was really made; hiding it would edit the record.
        expect(rows()).toHaveLength(2);
        expect(rows()[0].className).toContain('is-detached');
    });
});

// ── recall prose leaves the image ───────────────────────────────────────────
function Stage({ caption, note = '' }) {
    return (
        <div className="diff-stage-col">
            <div className="diff-stage"><img alt="" /></div>
            {caption && (
                <div className="diff-recall-say" role="status" aria-live="polite">
                    <p className="diff-recall-caption">{caption}</p>
                    {note && <p className="diff-recall-detached">{note}</p>}
                </div>
            )}
        </div>
    );
}

describe('recall prose does not sit on the image', () => {
    // The stage is the evidence surface. A paragraph-length percept laid over the
    // body covered the very grounds it was citing — the interpretation occluded
    // its own evidence.
    it('renders the caption OUTSIDE the stage element', async () => {
        await mount(<Stage caption="the exposure of the neck reads as erotic" />);
        const stage = container.querySelector('.diff-stage');
        const say = container.querySelector('.diff-recall-say');
        expect(say).not.toBeNull();
        expect(stage.contains(say)).toBe(false);
    });

    it('leaves no prose block inside the stage at all', async () => {
        await mount(<Stage caption="a long percept that would once have covered the body" note="one ground no longer resolves" />);
        expect(container.querySelector('.diff-stage .diff-recall-say')).toBeNull();
        expect(container.querySelector('.diff-stage .diff-recall-caption')).toBeNull();
        expect(container.querySelector('.diff-stage p')).toBeNull();
    });

    it('keeps the detached-evidence note out of the image too', async () => {
        await mount(<Stage caption="the answering hand" note="one ground no longer resolves" />);
        const detached = container.querySelector('.diff-recall-detached');
        expect(detached).not.toBeNull();
        expect(container.querySelector('.diff-stage').contains(detached)).toBe(false);
    });

    it('keeps the caption announced to screen readers', async () => {
        await mount(<Stage caption="the answering hand" />);
        const status = container.querySelector('[role="status"]');
        expect(status.getAttribute('aria-live')).toBe('polite');
        expect(status.textContent).toContain('the answering hand');
    });

    it('renders no strip at all when recall is not speaking', async () => {
        await mount(<Stage caption="" />);
        expect(container.querySelector('.diff-recall-say')).toBeNull();
    });
});
