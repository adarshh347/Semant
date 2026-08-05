import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import WriterStudio from './WriterStudio';
import { writerService } from './writerService';

/**
 * Semant Writer · W1 — the studio, mounted.
 *
 * The backend suite owns the invariants. This owns the BOUNDARY: that the surface does
 * not quietly undo them.
 *
 *   - a refused directive is shown as a result with its reason, not swallowed as an error
 *     and not given an Accept button;
 *   - a rendered passage is labelled quarantined and commits only on an explicit Accept;
 *   - `//` staging is rendered apart from the prose, never inside it.
 */

const RENDERED = {
    line: 4,
    directive: '/ threshold',
    operators: ['threshold'],
    orchestration: { goal: 'she arrives at the door', voice: 'close third' },
    status: 'ok',
    text: 'The latch gave before she had decided to push it.',
    refusal: '',
    provenance: { operators: [{ name: 'threshold', version: 1 }], intents: [] },
    diagnostics: [],
    passage_id: 'psg_1',
};

const REFUSED = {
    line: 5,
    directive: '/ ekstasis',
    operators: ['ekstasis'],
    orchestration: {},
    status: 'refused',
    text: '',
    refusal: 'undefined operator: `ekstasis`. Define with `#create ekstasis: …` first.',
    provenance: {},
    diagnostics: [],
    passage_id: null,
};

let container, root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.spyOn(writerService, 'listOperators').mockResolvedValue([
        { id: 'op_1', name: 'threshold', version: 1, definition: 'a crossing noticed late' },
    ]);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
});

async function mount(props = {}) {
    await act(async () => {
        root.render(<WriterStudio projectId="ms_1" sceneId="sc_1" {...props} />);
    });
}

async function runBlock(results) {
    vi.spyOn(writerService, 'run').mockResolvedValue({ results, proposals: [], diagnostics: [] });
    const textarea = container.querySelector('#writer-block-input');
    await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value',
        ).set;
        setter.call(textarea, '/ threshold');
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const button = [...container.querySelectorAll('button')]
        .find((b) => b.textContent === 'Render');
    await act(async () => { button.click(); });
}

describe('WriterStudio', () => {
    it('lists the author operators it was given', async () => {
        await mount();
        expect(container.textContent).toContain('threshold');
        expect(container.textContent).toContain('a crossing noticed late');
    });

    it('shows a refusal as a result with its reason, and offers no Accept', async () => {
        await mount();
        await runBlock([REFUSED]);

        expect(container.textContent).toContain('undefined operator');
        expect(container.textContent).toContain('#create ekstasis');
        expect(container.querySelector('.writer-error')).toBeNull();   // not an error
        expect(container.querySelector('.writer-result--refused')).not.toBeNull();
        const buttons = [...container.querySelectorAll('.writer-result button')]
            .map((b) => b.textContent);
        expect(buttons).not.toContain('Accept');
    });

    it('labels a rendered passage quarantined and commits only on Accept', async () => {
        const accept = vi.spyOn(writerService, 'accept').mockResolvedValue({});
        await mount();
        await runBlock([RENDERED]);

        expect(container.querySelector('.writer-quarantined').textContent).toBe('quarantined');
        expect(accept).not.toHaveBeenCalled();          // nothing auto-commits

        const button = [...container.querySelectorAll('button')]
            .find((b) => b.textContent === 'Accept');
        await act(async () => { button.click(); });

        expect(accept).toHaveBeenCalledWith('psg_1', 'sc_1');
        expect(container.textContent).toContain('accepted');
        expect([...container.querySelectorAll('button')].map((b) => b.textContent))
            .not.toContain('Accept');                   // a decision is made once
    });

    it('renders // staging apart from the prose, never inside it', async () => {
        await mount();
        await runBlock([RENDERED]);

        const staging = container.querySelector('.writer-staging');
        const passage = container.querySelector('.writer-passage');
        expect(staging.textContent).toContain('she arrives at the door');
        expect(passage.textContent).toBe('The latch gave before she had decided to push it.');
        expect(passage.textContent).not.toContain('goal');
        expect(passage.textContent).not.toContain('//');
    });

    it('shows provenance for a rendered passage', async () => {
        await mount();
        await runBlock([RENDERED]);
        expect(container.querySelector('.writer-provenance').textContent)
            .toContain('threshold v1');
    });
});
