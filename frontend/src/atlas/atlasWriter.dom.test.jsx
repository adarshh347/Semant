/**
 * ATLAS C5 — the writer, mounted.
 *
 * `atlasDraft.test.js` pins what the draft IS; this pins what a writer SEES and can do. Four
 * things have to render or the surface is quietly dishonest:
 *
 *   the draft says it is a proposal, before it says anything else
 *   what the article could not carry is on screen beside the Accept button
 *   a citation that could not be drawn is admitted, not silently missing
 *   Accept is unavailable when there is no prose to accept
 *
 * And one thing has to be impossible: nothing may leave quarantine without the writer's click.
 * That is asserted against the actual calls the panel makes.
 *
 * Every fixture is synthetic. No backend, no model, no real post.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasWriterPanel from './AtlasWriterPanel.jsx';
import { BLOCK_NO_PLAN, DRAFT_ACCEPTED, DRAFT_QUARANTINED } from './atlasDraft.js';

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const click = async (el) => {
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
};
const text = () => container.textContent;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

// ── fixtures ────────────────────────────────────────────────────────────────

const aPlan = () => ({
    thesis: 'the sequence disperses what the rotunda gathers',
    claims: [{
        claim_id: 'c0', text: 'the field disperses', status: 'supported', struck: false,
        percepts: [{ step_id: 'c0:0:negative_space', actuator: 'negative_space',
            function: 'support', epistemic: 'measured', image: 'p1', bound: true }],
    }],
});

const aSection = (over = {}) => ({
    claim_id: 'c0', claim: 'the field disperses', prose: 'The field concentrates left.',
    epistemic: 'measured', function: 'support', qualified: false, caveats: [],
    relevance_flags: [], uncited_mentions: [],
    citations: [{ step_id: 'c0:0:negative_space', actuator: 'negative_space',
        function: 'support', epistemic: 'measured', image: 'p1' }],
    ...over,
});

const aDraft = ({ inner = {}, resolved = null, counts = null, state = DRAFT_QUARANTINED } = {}) => ({
    state,
    thesis: 'the sequence disperses what the rotunda gathers',
    article: {
        draft: {
            thesis: 'the sequence disperses what the rotunda gathers',
            thesis_prose: 'An opening paragraph.',
            sections: [aSection()], uncomposed: [], qualifications: [],
            counter_reading: null, committed: false, complete: true, epistemic: 'measured',
            ...inner,
        },
        resolved: resolved ?? {
            'c0:0:negative_space': {
                step_id: 'c0:0:negative_space', actuator: 'negative_space', status: 'resolved',
                image: 'p1', image_ref: 'https://example.invalid/p1.jpg', image_title: 'p1',
                geometry: { kind: 'brush_field', cells: [[0, 0, 0.4]] },
                geometry_kind: 'brush_field', label: 'the open field', drawable: true,
                source_ref: 'sug_1', detail: '', candidates: [],
                reopen: { post_id: 'p1', source_ref: 'sug_1', step_id: 'c0:0:negative_space' },
            },
        },
        counts: counts ?? { citations: 1, drawable: 1, unresolved: 0 },
    },
});

const noop = () => {};
const props = (over = {}) => ({
    plan: aPlan(), draft: null, blocker: null, onDraft: noop, drafting: false,
    onAccept: noop, accepting: false, onDismiss: noop, onExport: noop, error: '', ...over,
});

// ── 1. the seed, before anything is drafted ────────────────────────────────

describe('the seed', () => {
    it('shows the claims the draft will be written from, with their percepts', async () => {
        await mount(<AtlasWriterPanel {...props()} />);
        expect(text()).toContain('the field disperses');
        expect(text()).toContain('negative_space');
        expect(container.querySelector('[data-step-id="c0:0:negative_space"]')).toBeTruthy();
    });

    it('says that drafting runs the producers for real', async () => {
        await mount(<AtlasWriterPanel {...props()} />);
        expect(text()).toContain('runs those producers for real');
    });

    it('renders the blocker instead of a draft button that would refuse', async () => {
        await mount(<AtlasWriterPanel {...props({ plan: null, blocker: BLOCK_NO_PLAN })} />);
        expect(text()).toContain('No plan has been accepted');
        expect(container.querySelector('.atlas-w-seed')).toBeNull();
    });

    it('drafts only when the writer asks', async () => {
        const onDraft = vi.fn();
        await mount(<AtlasWriterPanel {...props({ onDraft })} />);
        expect(onDraft).not.toHaveBeenCalled();          // nothing composes on mount
        await click(container.querySelector('.atlas-go'));
        expect(onDraft).toHaveBeenCalledTimes(1);
    });
});

// ── 2. the draft says it is a proposal ─────────────────────────────────────

describe('the quarantine, on screen', () => {
    it('says the prose is proposed and not yet the writer\'s', async () => {
        await mount(<AtlasWriterPanel {...props({ draft: aDraft() })} />);
        expect(text()).toContain('Quarantined');
        expect(text()).toContain('proposed, not yet yours');
    });

    it('renders M4\'s own article, so the preview and the export are one document', async () => {
        await mount(<AtlasWriterPanel {...props({ draft: aDraft() })} />);
        // The renderer's own root, mounted unchanged — not a second article drawn for the panel.
        const article = container.querySelector('.art-root');
        expect(article).toBeTruthy();
        expect(article.getAttribute('data-committed')).toBe('false');
        expect(text()).toContain('The field concentrates left.');
    });

    it('offers no editor on a quarantined draft', async () => {
        // An editable suggestion would erase the distinction between what the model proposed and
        // what the writer committed.
        await mount(<AtlasWriterPanel {...props({
            draft: aDraft(), editor: <div data-testid="editor">the manuscript editor</div> })} />);
        expect(container.querySelector('[data-testid="editor"]')).toBeNull();
    });

    it('opens the existing editor only once the prose has been accepted', async () => {
        await mount(<AtlasWriterPanel {...props({
            draft: aDraft({ state: DRAFT_ACCEPTED }),
            editor: <div data-testid="editor">the manuscript editor</div> })} />);
        expect(container.querySelector('[data-testid="editor"]')).toBeTruthy();
        expect(text()).toContain('Accepted into the manuscript');
    });

    it('counts live percepts against cited ones', async () => {
        await mount(<AtlasWriterPanel {...props({ draft: aDraft() })} />);
        expect(text()).toContain('1/1 percepts live');
    });
});

// ── 3. live percepts, and honest failure to draw one ───────────────────────

describe('the evidence beside the prose', () => {
    it('draws the cited percept on its own source image', async () => {
        await mount(<AtlasWriterPanel {...props({ draft: aDraft() })} />);
        const figure = container.querySelector('.art-figures');
        expect(figure).toBeTruthy();
        expect(container.innerHTML).toContain('https://example.invalid/p1.jpg');
    });

    it('reopens a percept on its source image, with the step it came from', async () => {
        const onReopen = vi.fn();
        await mount(<AtlasWriterPanel {...props({ draft: aDraft(), onReopen })} />);
        const open = container.querySelector('.art-figure-open');
        expect(open, 'a live percept must be reopenable').toBeTruthy();

        await click(open);
        expect(onReopen).toHaveBeenCalledTimes(1);
        const [target, citation] = onReopen.mock.calls[0];
        expect(target.postId).toBe('p1');
        // The step travels with the link. Reopening the right POST and the wrong percept is the
        // failure a reader would never catch.
        expect(target.href).toContain('step=c0%3A0%3Anegative_space');
        expect(citation.step_id).toBe('c0:0:negative_space');
    });

    it('admits a citation it could not draw instead of showing an empty figure', async () => {
        const draft = aDraft({
            resolved: {
                'c0:0:negative_space': {
                    step_id: 'c0:0:negative_space', actuator: 'negative_space',
                    status: 'unproduced', image: 'p1', geometry: null, drawable: false,
                    detail: 'no produced percept matches \'negative_space\' on p1',
                    candidates: [], reopen: null,
                },
            },
            counts: { citations: 1, drawable: 0, unresolved: 1 },
        });
        await mount(<AtlasWriterPanel {...props({ draft })} />);
        expect(text()).toContain('1 could not be shown');
        expect(text()).toContain('no produced percept matches');
    });
});

// ── 4. refusals render beside the Accept button ────────────────────────────

describe('what the article could not carry', () => {
    it('renders a qualification at full weight, not behind a disclosure triangle', async () => {
        const draft = aDraft({ inner: {
            qualifications: [{ claim_id: 'c1', status: 'refused',
                prose: 'The corpus could not carry the second claim.' }] } });
        await mount(<AtlasWriterPanel {...props({ draft })} />);
        const banner = container.querySelector('.atlas-banner.is-refused');
        expect(banner).toBeTruthy();
        expect(banner.textContent).toContain('could not carry the second claim');
        expect(container.querySelector('.atlas-banner.is-refused details')).toBeNull();
    });

    it('renders an uncomposed claim as a limit saying why it was not written', async () => {
        const draft = aDraft({ inner: {
            uncomposed: [{ claim_id: 'c1', claim: 'the rotunda gathers',
                reason: 'claim_was_not_confirmed_by_a_run', detail: 'the run did not confirm it' }] } });
        await mount(<AtlasWriterPanel {...props({ draft })} />);
        expect(text()).toContain('the rotunda gathers');
        expect(text()).toContain('not written');
    });

    it('renders a section\'s admitted defect beside its prose', async () => {
        const draft = aDraft({ inner: { sections: [aSection({
            uncited_mentions: ['p2'],
            relevance_flags: [{ actuator: 'rhythm', why: 'it measures a different thing' }] })] } });
        await mount(<AtlasWriterPanel {...props({ draft })} />);
        expect(text()).toContain('admitted defect');
        expect(text()).toContain('does not bear on this claim');
        expect(text()).toContain('names an image this section does not cite');
    });
});

// ── 5. nothing leaves quarantine without the writer ────────────────────────

describe('accept and dismiss', () => {
    it('accepts only on the writer\'s click', async () => {
        const onAccept = vi.fn();
        await mount(<AtlasWriterPanel {...props({ draft: aDraft(), onAccept })} />);
        expect(onAccept).not.toHaveBeenCalled();
        const button = [...container.querySelectorAll('button')]
            .find((b) => b.textContent.includes('Accept into the manuscript'));
        await click(button);
        expect(onAccept).toHaveBeenCalledTimes(1);
    });

    it('cannot accept a draft that composed no prose, and says why', async () => {
        const draft = aDraft({ inner: { sections: [] },
            counts: { citations: 0, drawable: 0, unresolved: 0 } });
        await mount(<AtlasWriterPanel {...props({ draft })} />);
        const button = [...container.querySelectorAll('button')]
            .find((b) => b.textContent.includes('Accept into the manuscript'));
        expect(button.disabled).toBe(true);
        expect(text()).toContain('composed no prose');
    });

    it('offers no Accept or Dismiss once the draft has been accepted', async () => {
        await mount(<AtlasWriterPanel {...props({ draft: aDraft({ state: DRAFT_ACCEPTED }) })} />);
        const labels = [...container.querySelectorAll('button')].map((b) => b.textContent);
        expect(labels.some((l) => l.includes('Accept into the manuscript'))).toBe(false);
        expect(labels.some((l) => l.includes('Dismiss'))).toBe(false);
    });

    it('exports without accepting — the artifact is a read', async () => {
        const onExport = vi.fn();
        const onAccept = vi.fn();
        await mount(<AtlasWriterPanel {...props({ draft: aDraft(), onExport, onAccept })} />);
        const button = [...container.querySelectorAll('button')]
            .find((b) => b.textContent.includes('Export'));
        await click(button);
        expect(onExport).toHaveBeenCalledTimes(1);
        expect(onAccept).not.toHaveBeenCalled();
    });

    it('dismisses on the writer\'s click', async () => {
        const onDismiss = vi.fn();
        await mount(<AtlasWriterPanel {...props({ draft: aDraft(), onDismiss })} />);
        const button = [...container.querySelectorAll('button')]
            .find((b) => b.textContent.includes('Dismiss'));
        await click(button);
        expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('renders an error as an alert rather than swallowing it', async () => {
        await mount(<AtlasWriterPanel {...props({ error: 'The draft was not accepted.' })} />);
        const alert = container.querySelector('[role="alert"]');
        expect(alert.textContent).toContain('The draft was not accepted.');
    });
});
