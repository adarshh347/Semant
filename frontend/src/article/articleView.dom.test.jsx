/**
 * CIRCUIT-003 M4 — the perceptual article renderer: DOM tests.
 *
 * The claims this gate exists to prove:
 *   1. A section renders its embedded LIVE geometry on its source image  → live percepts
 *   2. uncited_mentions and relevance_flags RENDER                       → the defect channel
 *   3. A gaps() claim renders as a qualification, never as a section     → qualifications
 *   4. Clicking a percept reopens it on its source image                 → reopen-on-source
 *   5. The article is read-only — no Accept, no commit                   → read-only
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ArticleView from './ArticleView.jsx';
import { containBox } from './PerceptFigure.jsx';
import {
    articleBlocks, articleDefects, reopenTarget, sectionCitations, sectionDefects,
} from './articleDraft.js';

const GROUND = 'post_lustgarten';
const ROTUNDA = 'post_rotunda';

const citation = (over = {}) => ({
    step_id: 'c0:0:pressure_zone', actuator: 'pressure_zone', function: 'support',
    epistemic: 'measured', image: GROUND, image_title: 'Lustgarten', attribution: null, ...over,
});

const resolved = (over = {}) => ({
    step_id: 'c0:0:pressure_zone', actuator: 'pressure_zone', function: 'support',
    epistemic: 'measured', status: 'resolved', image: GROUND,
    image_ref: 'data:image/png;base64,iVBORw0KGgo=', image_title: 'Lustgarten',
    geometry: { kind: 'raster', strokes: [[0.2, 0.3], [0.5, 0.5]] }, geometry_kind: 'raster',
    label: 'pressure zone', source_ref: 'lustgarten:pressure_zone', detail: '', candidates: [],
    drawable: true,
    reopen: { post_id: GROUND, source_ref: 'lustgarten:pressure_zone',
        step_id: 'c0:0:pressure_zone' },
    ...over,
});

function makeArticle(over = {}) {
    const {
        sectionOver = {}, resolvedOver = {}, draftOver = {},
    } = over;
    return {
        version: 1,
        counts: { citations: 1, drawable: 1, unresolved: 0 },
        images: [GROUND],
        resolved: { 'c0:0:pressure_zone': resolved(resolvedOver) },
        draft: {
            thesis: 'The museum converts a dispersed ground into a centralized interior.',
            thesis_prose: 'This reading follows the walk from the ground to the rotunda.',
            epistemic: 'measured', complete: false, committed: false, grounded: true,
            sections: [{
                claim_id: 'c0', claim: 'The ground disperses attention.', function: 'support',
                prose: 'The measured field spreads across the frame.',
                epistemic: 'measured', qualified: false, caveats: [],
                citations: [citation()], relevance_flags: [], dropped_citations: [],
                uncited_mentions: [], ...sectionOver,
            }],
            uncomposed: [],
            counter_reading: {
                grounded: true, prose: 'Read against itself, the field is weak evidence.',
                citations: [], absence_reason: '', absence_detail: '',
            },
            qualifications: [], notes: [], run_id: 'run_m4', model: 'fake/composer',
            ...draftOver,
        },
    };
}

// The project's DOM idiom: raw react-dom/client + act (no @testing-library).
let container; let root;

async function render(node) {
    await act(async () => { root.render(node); });
}

const text = () => container.textContent || '';
const q = (sel) => container.querySelector(sel);
const qa = (sel) => Array.from(container.querySelectorAll(sel));
const click = async (el) => { await act(async () => { el.click(); }); };

beforeEach(() => {
    // jsdom has no canvas 2d context; the field painter is exercised in its own suite.
    HTMLCanvasElement.prototype.getContext = vi.fn(() => null);
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

// ── 1. live percepts ─────────────────────────────────────────────────────────

describe('live percepts, embedded by reference', () => {
    it('renders the source image and the percept figure for a resolved citation', async () => {
        await render(<ArticleView article={makeArticle()} />);
        const figure = container.querySelector('[data-step-id="c0:0:pressure_zone"]');
        expect(figure).toBeTruthy();
        expect(figure.getAttribute('data-status')).toBe('resolved');
        const img = figure.querySelector('img.art-figure-img');
        expect(img).toBeTruthy();
        expect(img.getAttribute('src')).toContain('data:image/png');
        expect(img.getAttribute('alt')).toBe('Lustgarten');
    });

    it('carries the geometry kind onto the stage, so the renderer choice is inspectable', async () => {
        await render(<ArticleView article={makeArticle()} />);
        const stage = container.querySelector('.art-figure-stage');
        expect(stage.getAttribute('data-geometry-kind')).toBe('raster');
    });

    it('captions the figure with its function and its epistemic chip', async () => {
        await render(<ArticleView article={makeArticle()} />);
        const cap = container.querySelector('.art-figure-cap');
        expect(cap.textContent).toContain('support');
        const chip = cap.querySelector('.diff-epistemic-chip');
        expect(chip.getAttribute('data-epistemic')).toBe('measured');
    });

    it('renders the five-way epistemic legend', async () => {
        await render(<ArticleView article={makeArticle()} />);
        const legend = container.querySelector('.art-legend');
        for (const s of ['visible', 'measured', 'interpretive', 'sourced', 'uncertain']) {
            expect(legend.querySelector(`[data-epistemic="${s}"]`)).toBeTruthy();
        }
    });

    it('shows an unresolved percept as an honest placeholder, never an empty frame', async () => {
        const article = makeArticle({
            resolvedOver: {
                status: 'ambiguous', drawable: false, geometry: null,
                detail: '2 produced percepts match; none was chosen', candidates: ['a', 'b'],
            },
        });
        await render(<ArticleView article={article} />);
        const figure = container.querySelector('[data-step-id="c0:0:pressure_zone"]');
        expect(figure.className).toContain('is-unresolved');
        expect(figure.textContent).toContain('cannot be settled');
    });
});

// ── 2. THE HONEST-DEFECT CHANNEL ─────────────────────────────────────────────

describe('the honest-defect channel', () => {
    it('renders a relevance flag beside the prose it qualifies', async () => {
        const article = makeArticle({
            sectionOver: {
                qualified: true,
                relevance_flags: [{ step_id: 'c0:0:pressure_zone', actuator: 'pressure_zone',
                    why: 'it measures concentration, not spread' }],
            },
        });
        await render(<ArticleView article={article} />);
        const channel = container.querySelector('.art-defects');
        expect(channel).toBeTruthy();
        expect(channel.textContent).toContain('pressure_zone does not bear on this claim');
        expect(channel.textContent).toContain('it measures concentration, not spread');
        expect(channel.querySelector('[data-defect-kind="relevance"]')).toBeTruthy();
    });

    it('renders an uncited image mention', async () => {
        const article = makeArticle({ sectionOver: { uncited_mentions: [ROTUNDA] } });
        await render(<ArticleView article={article} />);
        const channel = container.querySelector('.art-defects');
        expect(channel.querySelector('[data-defect-kind="uncited"]')).toBeTruthy();
        expect(channel.textContent).toContain('names an image this section does not cite');
        expect(channel.textContent).toContain(ROTUNDA);
    });

    it('renders an unresolvable citation as a defect, not merely a blank figure', async () => {
        const article = makeArticle({
            resolvedOver: { status: 'ambiguous', drawable: false, geometry: null,
                detail: 'a suggestion does not record its step' },
        });
        await render(<ArticleView article={article} />);
        const channel = container.querySelector('.art-defects');
        expect(channel.querySelector('[data-defect-kind="unresolved"]')).toBeTruthy();
    });

    it('carries M3 caveats through verbatim', async () => {
        const article = makeArticle({
            sectionOver: { qualified: true, caveats: ["aimed to be 'visible', reached 'measured'"] },
        });
        await render(<ArticleView article={article} />);
        expect(container.querySelector('.art-defects').textContent)
            .toContain("aimed to be 'visible', reached 'measured'");
    });

    it('counts the admitted defects where a reader lands on them', async () => {
        const article = makeArticle({
            sectionOver: {
                uncited_mentions: [ROTUNDA],
                relevance_flags: [{ actuator: 'pressure_zone', why: 'unrelated' }],
            },
        });
        await render(<ArticleView article={article} />);
        expect(text()).toMatch(/2 admitted defects/);
    });

    it('shows no channel when a section admits nothing', async () => {
        await render(<ArticleView article={makeArticle()} />);
        expect(container.querySelector('.art-defects')).toBeNull();
    });
});

// ── 3. qualifications — never asserted ───────────────────────────────────────

describe('qualifications', () => {
    it('renders a refused claim as a qualification and never as a section', async () => {
        const article = makeArticle({
            draftOver: {
                qualifications: [{
                    claim_id: 'c3', claim: "The rotunda's stone recurs.", status: 'refused',
                    prose: 'This reading could not establish that the stone recurs.',
                    why: 'no_percept_could_be_produced',
                }],
            },
        });
        await render(<ArticleView article={article} />);
        const quals = container.querySelector('[data-block="qualifications"]');
        expect(quals).toBeTruthy();
        expect(quals.textContent).toContain('could not establish');
        // ...and it is NOT a section
        expect(container.querySelector('[data-claim-id="c3"].art-section')).toBeNull();
    });

    it('renders the ungrounded counter-reading as an absence, never an invented objection', async () => {
        const article = makeArticle({
            draftOver: {
                counter_reading: {
                    grounded: false, prose: '', citations: [],
                    absence_reason: 'no_challenge_percept_was_proposed',
                    absence_detail: 'The argument is therefore untested, not confirmed.',
                },
            },
        });
        await render(<ArticleView article={article} />);
        const counter = container.querySelector('[data-block="counter"]');
        expect(counter.textContent).toContain('No counter-reading could be grounded');
        expect(counter.textContent).toContain('untested, not confirmed');
        expect(counter.textContent).toContain('no_challenge_percept_was_proposed');
    });

    it('renders a grounded counter-reading as prose', async () => {
        await render(<ArticleView article={makeArticle()} />);
        const counter = container.querySelector('[data-block="counter"]');
        expect(counter.textContent).toContain('Read against itself');
    });
});

// ── 4. reopen-on-source ──────────────────────────────────────────────────────

describe('reopen-on-source', () => {
    it('a resolved percept is clickable and reopens on its source image', async () => {
        const onReopen = vi.fn();
        await render(<ArticleView article={makeArticle()} onReopen={onReopen} />);
        const button = container.querySelector('.art-figure-open');
        expect(button).toBeTruthy();
        await click(button);
        expect(onReopen).toHaveBeenCalledTimes(1);
        const [target, cited] = onReopen.mock.calls[0];
        expect(target.postId).toBe(GROUND);
        expect(target.href).toContain(`/posts/${GROUND}`);
        expect(target.href).toContain('percept=lustgarten%3Apressure_zone');
        expect(cited.step_id).toBe('c0:0:pressure_zone');
    });

    it('an unresolved percept is NOT clickable', async () => {
        const article = makeArticle({
            resolvedOver: { status: 'unproduced', drawable: false, geometry: null, reopen: null },
        });
        await render(<ArticleView article={article} />);
        expect(container.querySelector('.art-figure-open')).toBeNull();
    });

    it('reopenTarget carries the percept and the step, and refuses when unresolved', async () => {
        expect(reopenTarget({ reopen: { post_id: 'p1', source_ref: 'r', step_id: 's' } }).href)
            .toBe('/posts/p1?percept=r&step=s');
        expect(reopenTarget({ reopen: null })).toBeNull();
        expect(reopenTarget(null)).toBeNull();
    });
});

// ── 5. read-only ─────────────────────────────────────────────────────────────

describe('read-only', () => {
    it('says out loud that the draft is quarantined', async () => {
        await render(<ArticleView article={makeArticle()} />);
        expect(container.querySelector('.art-root').getAttribute('data-committed')).toBe('false');
        expect(text()).toMatch(/quarantined draft/i);
    });

    it('offers no accept, commit or edit control', async () => {
        await render(<ArticleView article={makeArticle()} />);
        const labels = Array.from(container.querySelectorAll('button'))
            .map((b) => (b.textContent || '').toLowerCase());
        for (const l of labels) {
            expect(l).not.toContain('accept');
            expect(l).not.toContain('commit');
            expect(l).not.toContain('publish');
        }
    });
});

// ── the pure layer ───────────────────────────────────────────────────────────

describe('articleDraft (pure)', () => {
    it('orders the blocks: opening, sections, counter, then limits last', async () => {
        const article = makeArticle({
            draftOver: { qualifications: [{ claim_id: 'c3', claim: 'x', status: 'refused',
                prose: 'p', why: 'w' }] },
        });
        expect(articleBlocks(article).map((b) => b.type))
            .toEqual(['opening', 'section', 'counter', 'qualifications']);
    });

    it('never drops a citation whose resolution is missing', async () => {
        const article = makeArticle();
        delete article.resolved['c0:0:pressure_zone'];
        const cites = sectionCitations(article.draft.sections[0], article);
        expect(cites).toHaveLength(1);
        expect(cites[0].status).toBe('unproduced');
        expect(cites[0].drawable).toBe(false);
    });

    it('collects every defect across the article', async () => {
        const article = makeArticle({
            sectionOver: { uncited_mentions: [ROTUNDA], caveats: ['a caveat'] },
        });
        const defects = articleDefects(article);
        expect(defects.map((d) => d.kind).sort()).toEqual(['caveat', 'uncited']);
        expect(defects.every((d) => d.claim_id === 'c0')).toBe(true);
    });

    it('sectionDefects reports nothing for a clean section', async () => {
        const article = makeArticle();
        expect(sectionDefects(article.draft.sections[0], article)).toEqual([]);
    });

    it('does not show a relevance mismatch twice', async () => {
        // Found in the rendered article: M3 records a mismatch structurally in `relevance_flags`
        // AND as prose in `caveats` (which is what the composer prompt is given). Rendering both
        // showed the reader the same admission twice, reading as two separate problems.
        const why = 'it measures concentration, not spread';
        const article = makeArticle({
            sectionOver: {
                relevance_flags: [{ actuator: 'pressure_zone', why }],
                caveats: [`pressure_zone does not bear on this claim: ${why}`],
            },
        });
        const defects = sectionDefects(article.draft.sections[0], article);
        expect(defects).toHaveLength(1);
        expect(defects[0].kind).toBe('relevance');
    });

    it('still shows a caveat that is not a restatement of a flag', async () => {
        const article = makeArticle({
            sectionOver: {
                relevance_flags: [{ actuator: 'pressure_zone', why: 'unrelated' }],
                caveats: ["aimed to be 'visible', reached 'measured'"],
            },
        });
        expect(sectionDefects(article.draft.sections[0], article).map((d) => d.kind))
            .toEqual(['relevance', 'caveat']);
    });
});

// ── the field must land on the IMAGE, not the stage ──────────────────────────

describe('containBox — the letterboxed image rect', () => {
    // The field painter works in normalized IMAGE coordinates, so it must be given the rect the
    // image actually occupies. Painting across the stage skews the wash by the difference between
    // the two aspects — the same drift that put FindSimilar's overlay off its image. Found in the
    // rendered article, where the percept simply did not appear.
    it('pillarboxes a 4:3 image in a wider stage', () => {
        const box = containBox({ w: 400, h: 200 }, { w: 400, h: 300 });
        expect(box.h).toBe(200);
        expect(box.w).toBeCloseTo(266.67, 1);
        expect(box.x).toBeCloseTo(66.67, 1);
        expect(box.y).toBe(0);
    });

    it('letterboxes a wide image in a squarer stage', () => {
        const box = containBox({ w: 300, h: 300 }, { w: 600, h: 200 });
        expect(box.w).toBe(300);
        expect(box.h).toBe(100);
        expect(box.x).toBe(0);
        expect(box.y).toBe(100);
    });

    it('fills exactly when the aspects match', () => {
        const box = containBox({ w: 400, h: 300 }, { w: 800, h: 600 });
        expect(box).toEqual({ x: 0, y: 0, w: 400, h: 300 });
    });

    it('refuses to guess a box before either size is known', () => {
        expect(containBox(null, { w: 4, h: 3 })).toBeNull();
        expect(containBox({ w: 4, h: 3 }, null)).toBeNull();
        expect(containBox({ w: 0, h: 0 }, { w: 4, h: 3 })).toBeNull();
    });
});
