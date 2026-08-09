/**
 * INQUIRY WORKBENCH — underperformance as a first-class result, and taking the session away.
 *
 * The 002R rehearsal ended `EXHAUSTED` with a long perceptive VLM paragraph on screen and no way
 * to see that nothing had been compiled from it. Everything needed to understand that was already
 * in the record.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import DiagnosisCard from './DiagnosisCard.jsx';
import SessionExport, { CopyButton } from './SessionExport.jsx';
import {
    normalizeSession, downstreamOf, barrenAfter, earliestFailure,
} from './inquiryContract.js';
import {
    truncatedCompilerFixture, barrenFixture, stagedCompleteFixture, completedFixture,
    runningStagesFixture,
} from './inquiryFixtures.js';

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
    vi.restoreAllMocks();
});

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const click = async (el) => { await act(async () => { el.click(); }); };

async function diagnose(fixture) {
    const session = normalizeSession(fixture);
    await act(async () => { root.render(<DiagnosisCard session={session} />); });
    return session;
}

// ── when it appears ─────────────────────────────────────────────────────────

describe('the diagnosis card', () => {
    it('does not appear for a run that completed properly', async () => {
        await diagnose(stagedCompleteFixture());
        expect($('[data-diagnosis="open"]')).toBeNull();
    });

    it('appears OPEN for a truncated run — no toggle to find', async () => {
        // A collapsed diagnosis under a fluent paragraph is a diagnosis nobody reads.
        await diagnose(truncatedCompilerFixture());
        const card = $('[data-diagnosis="open"]');
        expect(card).toBeTruthy();
        expect(card.querySelector('[aria-expanded]')).toBeNull();
    });

    it('names the EARLIEST stage that underperformed, not the last', async () => {
        // Everything after a failure is a consequence of it. Naming a consequence as the cause
        // sends a reader to the wrong place.
        const raw = truncatedCompilerFixture();
        raw.stages = [...raw.stages, {
            attempt_id: 'stg_composer', stage: 'composer', outcome: 'thin', duration_ms: 900,
        }];
        await diagnose(raw);
        expect($('[data-failed-stage]').dataset.failedStage).toBe('compiler');
        expect($('.iw-diagnosis-head').textContent)
            .toBe('This run stopped short at the breaking the reading into claims stage.');
    });

    it('never phrases it as "nothing new was found"', async () => {
        // That describes an inquiry that looked and came back empty-handed. It is the wrong
        // description of a compiler that stopped mid-output, and it points at the wrong repair.
        await diagnose(truncatedCompilerFixture());
        expect(text()).not.toMatch(/nothing new was found|no new findings|found nothing new/i);
        expect(text()).toMatch(/ran out of room, not out of things to say/i);
    });
});

// ── what entered, what emerged ──────────────────────────────────────────────

describe('what entered and what emerged', () => {
    it('reports the stage\'s own counters', async () => {
        await diagnose(truncatedCompilerFixture());
        expect($('[data-entered="31"]').textContent).toBe('31 objects');
        expect($('[data-emerged="2"]').textContent).toBe('2 objects');
        expect(text()).toContain('31 reading blocks entered; 2 claims and 0 observables emerged.');
    });

    it('says "not recorded" rather than inventing a count', async () => {
        const raw = barrenFixture();
        raw.stages = raw.stages.map((s) => (s.stage === 'compiler'
            ? { ...s, input_count: undefined, output_count: undefined,
                input_refs: undefined, output_refs: undefined }
            : s));
        await diagnose(raw);
        expect($('[data-entered="null"]').textContent).toBe('not recorded');
        expect($('[data-emerged="null"]').textContent).toBe('not recorded');
    });

    it('shows the finish reason and explains what `length` means', async () => {
        await diagnose(truncatedCompilerFixture());
        expect($('[data-finish="length"]').textContent)
            .toMatch(/length.*ran out of output budget, not out of things to say/s);
    });

    it('shows the call count when the stage supplied one', async () => {
        await diagnose(truncatedCompilerFixture());
        expect(text()).toContain('1 of 1 planned');
        expect(text()).toContain('21.4s');
    });
});

// ── what therefore did not happen ───────────────────────────────────────────

describe('the downstream consequences', () => {
    it('separates stages that NEVER RAN from stages that ran and produced nothing', async () => {
        // Different facts, and a reader deciding what to fix needs to know which.
        const session = await diagnose(truncatedCompilerFixture());
        const down = $('[data-downstream="true"]');
        expect(down.textContent).toMatch(/Never ran:.*Running a capability/);
        expect(down.textContent).toMatch(/Ran and produced nothing:.*Deciding what to ask you \(skipped\)/);

        expect(downstreamOf('compiler', session.stages))
            .toEqual(['capability', 'judge', 'composer']);
        expect(barrenAfter('compiler', session.stages).map((s) => s.stage.value))
            .toEqual(['steward']);
    });

    it('computes the downstream set from the declared order, not from guesswork', () => {
        expect(downstreamOf('theorist', [])).toEqual(
            ['compiler', 'steward', 'capability', 'judge', 'composer']);
        expect(downstreamOf('composer', [])).toEqual([]);
        expect(downstreamOf('nonsense', [])).toEqual([]);
        expect(barrenAfter('nonsense', [])).toEqual([]);
        expect(earliestFailure([])).toBeNull();
    });
});

// ── is the visible text only the reading ────────────────────────────────────

describe('when the only prose is the scene reading', () => {
    it('says so before the reading is reached', async () => {
        // The exact shape of the 002R rehearsal: an abundant paragraph standing in for an inquiry
        // that never happened.
        await diagnose(barrenFixture());
        const note = $('[data-reading-only="true"]');
        expect(note.textContent).toMatch(/The prose below is the scene reading, and only that/);
        expect(note.textContent)
            .toMatch(/one model's impression of the pictures rather than an inquiry into them/);
        expect(note.textContent).toMatch(/kept because it is often worth having/);
    });

    it('does not say so when claims were produced', async () => {
        await diagnose(truncatedCompilerFixture());
        expect($('[data-reading-only="true"]')).toBeNull();
    });
});

describe('the execution topology', () => {
    it('names live and fixture so a replay cannot be mistaken for a model failure', async () => {
        await diagnose(truncatedCompilerFixture());
        expect($('[data-topology-modes]').dataset.topologyModes).toBe('live');
        expect(text()).toContain('Stage execution: live.');
        expect(text()).toMatch(/one capability is a declared simulation either way/);
    });

    it('says so plainly when no stage declared a mode', async () => {
        const raw = barrenFixture();
        raw.stages = raw.stages.map((s) => ({ ...s, actor: undefined, execution_mode: undefined }));
        await diagnose(raw);
        expect(text()).toMatch(/No stage declared whether it ran live or from a fixture/);
    });

    it('carries the stop reason and any recorded gaps', async () => {
        const raw = barrenFixture();
        raw.gaps = ['no geometry family is registered'];
        await diagnose(raw);
        expect($('[data-stop-reason="true"]').textContent)
            .toBe('Nothing was compiled from the reading.');
        expect(text()).toContain('no geometry family is registered');
    });
});

// ── export ──────────────────────────────────────────────────────────────────

describe('taking the session away', () => {
    async function mountExport(fixture, download) {
        const session = normalizeSession(fixture);
        await act(async () => {
            root.render(<SessionExport session={session} download={download} />);
        });
        return session;
    }

    it('exports the BACKEND\'s body, not this page\'s reading of it', async () => {
        // The normalised object contains fields this client derived — `running`, `simulated`,
        // counts inferred from ref arrays. A file mixing those in would let a reader attribute a
        // client-side inference to the backend.
        const saved = [];
        const raw = completedFixture();
        await mountExport(raw, (name, json) => saved.push([name, json]));
        await click($('[data-download-session="true"]'));

        expect(saved).toHaveLength(1);
        const [name, json] = saved[0];
        expect(name).toBe('inquiry-inqs_fixture_1-rev7.json');
        const body = JSON.parse(json);
        expect(body).toEqual(raw);
        // none of the client's derived vocabulary reached the file
        expect(json).not.toContain('"running"');
        expect(json).not.toContain('"underperformed"');
        expect(json).not.toContain('"label_is_id"');
    });

    it('round-trips: the export re-normalises to the same session', async () => {
        const saved = [];
        await mountExport(stagedCompleteFixture(), (n, j) => saved.push(j));
        await click($('[data-download-session="true"]'));
        const reread = normalizeSession(JSON.parse(saved[0]));
        const original = normalizeSession(stagedCompleteFixture());
        expect(JSON.stringify(reread)).toBe(JSON.stringify(original));
    });

    it('names the file by session AND revision', async () => {
        // Two exports of the same session at different revisions are different documents.
        await mountExport(runningStagesFixture(), () => {});
        expect($('[data-download-session="true"]').dataset.filename)
            .toBe('inquiry-inqs_fixture_1-rev2.json');
    });

    it('offers copyable ids, and reports a clipboard that refused', async () => {
        await mountExport(completedFixture(), () => {});
        expect($('[data-copy-value="inqs_fixture_1"]')).toBeTruthy();
        expect($('[data-copy-value="sig_fixture_1"]')).toBeTruthy();

        // Saying "Copied" after a rejected write costs a person the thing they were about to paste.
        await act(async () => {
            root.render(<CopyButton value="x" label="Copy id" />);
        });
        await click($('.iw-copy'));
        await act(async () => { await Promise.resolve(); });
        expect($('.iw-copy').textContent).toBe('Could not copy');
    });

    it('says "Copied" when the clipboard took it', async () => {
        const writeText = vi.fn(async () => {});
        vi.stubGlobal('navigator', { clipboard: { writeText } });
        await act(async () => { root.render(<CopyButton value="abc" />); });
        await click($('.iw-copy'));
        await act(async () => { await Promise.resolve(); });
        expect(writeText).toHaveBeenCalledWith('abc');
        expect($('.iw-copy').textContent).toBe('Copied');
        vi.unstubAllGlobals();
    });

    it('quarantines model text the backend refused, away from the graph', async () => {
        const raw = {
            ...barrenFixture(),
            quarantined_text: '{"claims": [ ...unterminated',
        };
        await mountExport(raw, () => {});
        const quarantine = $('[data-quarantine="true"]');
        expect(quarantine.textContent).toMatch(/backend refused this output and kept it aside/);
        expect(quarantine.textContent).toMatch(/supports nothing/);
        expect(quarantine.querySelector('.iw-quarantine-text').textContent)
            .toBe('{"claims": [ ...unterminated');
    });

    it('shows no quarantine block when there is nothing quarantined', async () => {
        await mountExport(completedFixture(), () => {});
        expect($('[data-quarantine="true"]')).toBeNull();
    });
});
