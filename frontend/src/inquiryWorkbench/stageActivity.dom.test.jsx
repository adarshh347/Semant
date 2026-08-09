/**
 * INQUIRY WORKBENCH — the machinery, while it runs.
 *
 * The 002R rehearsal's fourth tree cause: the backend recorded every stage transition and this
 * client never read the list, so a person watched `Starting…` with no idea which of seven stages
 * was taking the time.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import StageActivity from './StageActivity.jsx';
import { normalizeSession, formatDuration, stageElapsedMs, currentStage, underperformingStages }
    from './inquiryContract.js';
import {
    runningStagesFixture, truncatedCompilerFixture, barrenFixture, stagedCompleteFixture,
    unknownStageFixture,
} from './inquiryFixtures.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.useRealTimers();
    vi.restoreAllMocks();
});

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => { await act(async () => { el.click(); }); };

/** A fixed clock, so an elapsed time is an assertion rather than a race. */
const NOW = Date.parse('2026-08-09T09:14:44Z');

async function mount(fixture, props = {}) {
    const session = normalizeSession(fixture);
    await act(async () => {
        root.render(
            <StageActivity stages={session.stages} working now={NOW} {...props} />);
    });
    return session;
}

// ── the running case ────────────────────────────────────────────────────────

describe('a session that is working', () => {
    it('names the stage that is running and the ones that finished', async () => {
        await mount(runningStagesFixture());
        expect($$('.iw-stage')).toHaveLength(2);
        expect($('[data-stage="framer"]').dataset.outcome).toBe('completed');
        const theorist = $('[data-stage="theorist"]');
        expect(theorist.dataset.outcome).toBe('started');
        expect(theorist.textContent).toContain('Looking at the images');
        expect(theorist.querySelector('.iw-pulse')).toBeTruthy();
    });

    it('counts elapsed time from the stage\'s OWN start, not from now', async () => {
        // started_at 09:14:02, clock 09:14:44 → 42 seconds.
        await mount(runningStagesFixture());
        const elapsed = $('[data-stage="theorist"] [data-elapsed="true"]');
        expect(elapsed.textContent).toBe('42.0s elapsed');
        // the finished stage shows no elapsed at all
        expect($('[data-stage="framer"] [data-elapsed="true"]')).toBeNull();
    });

    it('ticks while a stage is running, and only while one is', async () => {
        vi.useFakeTimers();
        const running = normalizeSession(runningStagesFixture());
        // No pinned `now` — the component runs its own clock, which is the browser behaviour.
        vi.setSystemTime(Date.parse('2026-08-09T09:14:12Z'));
        await act(async () => {
            root.render(<StageActivity stages={running.stages} working />);
        });
        expect($('[data-elapsed="true"]').textContent).toBe('10.0s elapsed');

        // `advanceTimersByTime` moves the mocked clock too, so the elapsed figure is the sum
        // rather than something to set separately.
        await act(async () => { vi.advanceTimersByTime(3000); });
        expect($('[data-elapsed="true"]').textContent).toBe('13.0s elapsed');

        // A finished session starts no interval — nothing to count.
        const done = normalizeSession(stagedCompleteFixture());
        await act(async () => {
            root.render(<StageActivity stages={done.stages} working={false} open />);
        });
        expect(vi.getTimerCount()).toBe(0);
    });

    it('invents no percentage and no estimated finish', async () => {
        await mount(runningStagesFixture());
        // The inquiry does not know how long a model call takes or how many claims will come
        // back, so a bar would be inventing a denominator and an ETA a rate.
        expect($('progress')).toBeNull();
        expect($('[role="progressbar"]')).toBeNull();
        expect(text()).not.toMatch(/%|remaining|estimated|about \d+ (second|minute)/i);
    });

    it('reports multi-image progress from the stage\'s own counters', async () => {
        await mount(runningStagesFixture());
        const progress = $('[data-image-progress="true"]');
        expect(progress.textContent).toContain('image 2 of 4');
        expect(progress.textContent).toContain('reading image 2');
    });

    it('reports the declared call topology and plan, never a derived one', async () => {
        // "4 image readings plus one synthesis planned" is the backend's claim about its own plan.
        await mount(runningStagesFixture());
        const theorist = $('[data-stage="theorist"]');
        expect(theorist.querySelector('[data-topology]').textContent)
            .toBe('per image then synthesis');
        expect(theorist.querySelector('[data-planned-calls="5"]').textContent).toBe('2 of 5 calls');
    });

    it('names the model, the provider and the execution mode', async () => {
        await mount(runningStagesFixture());
        const theorist = $('[data-stage="theorist"]');
        expect(theorist.textContent).toContain('qwen/qwen3.6-27b');
        expect(theorist.textContent).toContain('groq');
        expect(theorist.querySelector('[data-execution-mode="live"]')).toBeTruthy();
    });

    it('says so plainly when a working session has reported no stage yet', async () => {
        await act(async () => { root.render(<StageActivity stages={[]} working />); });
        expect($('[data-stages="none"]').textContent)
            .toMatch(/not a session doing nothing/i);
    });
});

// ── durations that were never measured ──────────────────────────────────────

describe('a duration nobody measured', () => {
    it('renders as an em dash, never as 0 ms', async () => {
        await mount(truncatedCompilerFixture());
        const skipped = $('[data-stage="steward"] .iw-stage-duration');
        // The visible text is the em dash; `.iw-sr` carries the name a screen reader needs,
        // because a bare `—` reads aloud as "dash" and says nothing.
        expect(skipped.dataset.duration).toBe('null');
        expect(skipped.querySelector('.iw-sr').textContent).toBe('duration not reported');
        expect(skipped.lastChild.textContent).toBe('—');
        expect(text()).not.toContain('0 ms');
    });

    it('formats what was measured, at the scale it happened on', () => {
        expect(formatDuration(null)).toBe('—');
        expect(formatDuration(undefined)).toBe('—');
        expect(formatDuration(NaN)).toBe('—');
        expect(formatDuration(0)).toBe('0 ms');       // a real zero survives
        expect(formatDuration(840)).toBe('840 ms');
        expect(formatDuration(21400)).toBe('21.4s');
        expect(formatDuration(125000)).toBe('2m 05s');
    });

    it('refuses to count elapsed from an origin the stage never gave', () => {
        // A clock counting up from an unknown start is a fabricated measurement, and the most
        // believable kind.
        expect(stageElapsedMs({ running: true, started_at: null, queued_at: null, at: null }, NOW))
            .toBeNull();
        expect(stageElapsedMs({ running: false, started_at: '2026-08-09T09:14:02Z' }, NOW))
            .toBeNull();
        expect(stageElapsedMs(null, NOW)).toBeNull();
    });
});

// ── underperformance is visible at the stage ────────────────────────────────

describe('a stage that produced less than it should have', () => {
    it('does not wear the completed treatment', async () => {
        const session = await mount(truncatedCompilerFixture(), { working: false, open: true });
        const compiler = $('[data-stage="compiler"]');
        expect(compiler.dataset.outcome).toBe('truncated');
        expect(compiler.textContent)
            .toMatch(/what came back is a PREFIX/i);
        expect(compiler.textContent)
            .toMatch(/not evidence that there was little to find/i);
        expect(underperformingStages(session).map((s) => s.stage.value)).toEqual(['compiler']);
        expect(currentStage(session)).toBeNull();
    });

    it('shows the finish reason beside the stage, not buried in a receipt', async () => {
        // `finish_reason: length` is the single most consequential field the live runs produced.
        await mount(truncatedCompilerFixture(), { working: false, open: true });
        expect($('[data-finish-reason="length"]').textContent).toBe('finish: length');
    });

    it('carries the counts the stage gave — what entered and what emerged', async () => {
        await mount(truncatedCompilerFixture(), { working: false, open: true });
        const compiler = $('[data-stage="compiler"]');
        expect(compiler.textContent).toContain('in 31');
        expect(compiler.textContent).toContain('out 2');
        expect(compiler.textContent)
            .toContain('31 reading blocks entered; 2 claims and 0 observables emerged.');
    });

    it('separates a stage that returned nothing from one that was excluded', async () => {
        const session = await mount(barrenFixture(), { working: false, open: true });
        expect($('[data-stage="compiler"]').dataset.outcome).toBe('empty');
        expect($('[data-stage="steward"]').dataset.outcome).toBe('skipped');
        expect($('[data-stage="compiler"]').textContent)
            .toMatch(/Ran to completion and produced nothing/);
        expect($('[data-stage="steward"]').textContent).toMatch(/budget or the branch excluded it/);
        // and only the empty one counts as underperformance
        expect(underperformingStages(session).map((s) => s.stage.value)).toEqual(['compiler']);
    });
});

// ── forward and backward compatibility ──────────────────────────────────────

describe('reading two servers at once', () => {
    it('renders a v1 stage event that has only `at` and no actor block', async () => {
        // Today's `StageEvent` is event_id/stage/outcome/at/revision/detail/refs, and it must not
        // become unreadable because Lane B's richer one exists.
        const session = await mount(runningStagesFixture());
        const framer = session.stages[0];
        expect(framer.duration_ms).toBeNull();
        expect(framer.model).toBe('');
        expect($('[data-stage="framer"]').textContent).toContain('Reading your question');
        expect($('[data-stage="framer"] .iw-stage-duration').lastChild.textContent).toBe('—');
    });

    it('renders an unrecognised stage and outcome as themselves', async () => {
        await mount(unknownStageFixture(), { working: false, open: true });
        const future = $('[data-stage="unknown"]');
        expect(future.dataset.outcome).toBe('unknown');
        expect(future.textContent).toContain('resonator');
        expect(future.textContent).toContain('attuning');
        // nothing was rounded to a familiar neighbour
        expect($('[data-outcome="completed"]')).toBeTruthy();   // the framer, genuinely completed
        expect($('[data-stage="resonator"]')).toBeNull();
        expect(future.querySelector('.iw-exec--unknown')).toBeTruthy();
    });

    it('derives a count from refs but never invents one from nothing', async () => {
        const session = normalizeSession({
            stages: [
                { event_id: 'a', stage: 'framer', outcome: 'completed', output_refs: ['x', 'y'] },
                { event_id: 'b', stage: 'judge', outcome: 'completed' },
            ],
        });
        expect(session.stages[0].output_count).toBe(2);
        expect(session.stages[1].output_count).toBeNull();
        expect(session.stages[1].input_count).toBeNull();
    });
});

// ── the panel's own behaviour ───────────────────────────────────────────────

describe('the panel', () => {
    it('is open while working and collapsed once the session ends', async () => {
        await mount(runningStagesFixture());
        expect($('.iw-stage-list')).toBeTruthy();

        const done = normalizeSession(stagedCompleteFixture());
        await act(async () => {
            root.render(<StageActivity stages={done.stages} working={false} now={NOW} />);
        });
        // Reference material rather than the thing you are watching — but never gone.
        expect($('.iw-stage-list')).toBeNull();
        expect($('.iw-expand').textContent).toBe('Show 5 stages');
        await click($('.iw-expand'));
        expect($$('.iw-stage')).toHaveLength(5);
    });

    it('renders nothing at all for a finished session that recorded no stages', async () => {
        await act(async () => { root.render(<StageActivity stages={[]} working={false} />); });
        expect($('.iw-stages')).toBeNull();
    });
});

describe('the stylesheet keeps eleven outcomes apart', () => {
    const css = () => fs.readFileSync(path.join(HERE, 'inquiryWorkbench.css'), 'utf8');
    const rule = (selector) => {
        const m = css().match(new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`));
        return m ? m[1].replace(/\s+/g, ' ').trim() : null;
    };

    it('gives every stage outcome its own treatment', () => {
        const outcomes = ['queued', 'started', 'completed', 'thin', 'truncated', 'empty',
            'unavailable', 'refused', 'skipped', 'error', 'interrupted', 'unknown'];
        const seen = new Map();
        for (const o of outcomes) {
            const r = rule(`.iw-stage-outcome--${o}`);
            expect([o, r]).not.toEqual([o, null]);
            expect([o, seen.get(r)]).toEqual([o, undefined]);
            seen.set(r, o);
        }
    });

    it('never lets truncated or thin wear completed\'s treatment', () => {
        // The two the phase exists for: a parsed response with four claims and no observables is
        // not a completed compilation.
        expect(rule('.iw-stage--truncated')).not.toBe(rule('.iw-stage--completed'));
        expect(rule('.iw-stage--thin')).not.toBe(rule('.iw-stage--completed'));
        expect(rule('.iw-stage-outcome--truncated')).not.toBe(rule('.iw-stage-outcome--completed'));
        expect(rule('.iw-stage-outcome--thin')).not.toBe(rule('.iw-stage-outcome--completed'));
    });
});
